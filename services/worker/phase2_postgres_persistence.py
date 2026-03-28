from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _prediction_id(job_id: str, peptide_id: str) -> str:
    digest = hashlib.sha1(f"{job_id}:{peptide_id}".encode("utf-8")).hexdigest()  # noqa: S324
    return f"pred-{digest[:16]}"


def _stable_md5_for_path(path: str) -> str:
    file_path = Path(path)
    if file_path.exists() and file_path.is_file():
        return hashlib.md5(file_path.read_bytes()).hexdigest()  # noqa: S324
    return hashlib.md5(path.encode("utf-8")).hexdigest()  # noqa: S324


def persist_phase2_outputs(
    *,
    database_url: str,
    job_id: str,
    metadata: dict,
    pipeline_version: str,
    image_digest: str,
    model_version: str,
    parameters: dict,
    input_paths: list[str],
    variant_annotations_path: str,
    ranked_peptides_path: str,
    feature_table_path: str,
) -> dict:
    if not database_url:
        return {"enabled": False, "reason": "missing_database_url"}

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for Phase 2 PostgreSQL persistence. Install with: pip install psycopg[binary]"
        ) from exc

    patient_id = str(metadata.get("patient_id") or f"patient-{job_id}")
    sample_id = str(metadata.get("sample_id") or f"sample-{job_id}")
    project_id = str(metadata.get("project_id") or "ruo-default-project")
    consent_status = str(metadata.get("consent_status") or "research_use_only")
    sample_type = str(metadata.get("sample_type") or "tumor")
    run_id = str(metadata.get("run_id") or f"run-{job_id}")
    object_store_path = str(input_paths[0]) if input_paths else f"memory://{job_id}/input"
    read_type = metadata.get("read_type")
    platform = metadata.get("platform")

    variants = json.loads(Path(variant_annotations_path).read_text(encoding="utf-8"))
    ranked = json.loads(Path(ranked_peptides_path).read_text(encoding="utf-8"))
    features = json.loads(Path(feature_table_path).read_text(encoding="utf-8"))
    feature_map = {item.get("peptide_id"): item for item in features}

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patient (patient_id, consent_status, project_id, clinical_metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (patient_id) DO UPDATE
                SET consent_status = EXCLUDED.consent_status,
                    project_id = EXCLUDED.project_id,
                    clinical_metadata = EXCLUDED.clinical_metadata
                """,
                (patient_id, consent_status, project_id, json.dumps(metadata.get("clinical_metadata", {}))),
            )
            cur.execute(
                """
                INSERT INTO sample (sample_id, patient_id, sample_type, lims_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (sample_id) DO UPDATE
                SET patient_id = EXCLUDED.patient_id,
                    sample_type = EXCLUDED.sample_type,
                    lims_id = EXCLUDED.lims_id
                """,
                (sample_id, patient_id, sample_type, metadata.get("lims_id")),
            )
            cur.execute(
                """
                INSERT INTO sequence_run (run_id, sample_id, object_store_path, md5, platform, read_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (run_id) DO UPDATE
                SET sample_id = EXCLUDED.sample_id,
                    object_store_path = EXCLUDED.object_store_path,
                    md5 = EXCLUDED.md5,
                    platform = EXCLUDED.platform,
                    read_type = EXCLUDED.read_type,
                    metadata = EXCLUDED.metadata
                """,
                (
                    run_id,
                    sample_id,
                    object_store_path,
                    _stable_md5_for_path(object_store_path),
                    platform,
                    read_type,
                    json.dumps({"job_id": job_id, "run_mode": parameters.get("run_mode")}),
                ),
            )

            for variant in variants:
                variant_id = str(variant["variant_id"])
                cur.execute(
                    """
                    INSERT INTO variant (variant_id, sample_id, chr, pos, ref, alt, gene, effect, vaf, clonal_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (variant_id) DO UPDATE
                    SET sample_id = EXCLUDED.sample_id,
                        chr = EXCLUDED.chr,
                        pos = EXCLUDED.pos,
                        ref = EXCLUDED.ref,
                        alt = EXCLUDED.alt,
                        gene = EXCLUDED.gene,
                        effect = EXCLUDED.effect,
                        vaf = EXCLUDED.vaf,
                        clonal_status = EXCLUDED.clonal_status
                    """,
                    (
                        variant_id,
                        sample_id,
                        str(variant.get("chr") or "chr1"),
                        int(variant.get("position", 0)),
                        str(variant.get("ref") or "N"),
                        str(variant.get("alt") or "N"),
                        variant.get("gene"),
                        variant.get("effect"),
                        variant.get("vaf"),
                        "subclonal" if float(variant.get("vaf", 0.0)) < 0.3 else "clonal",
                    ),
                )

            for peptide in ranked:
                peptide_id = str(peptide["peptide_id"])
                source_variant_id = str(peptide["source_variant_id"])
                feature_snapshot = feature_map.get(peptide_id, {})
                prediction_id = _prediction_id(job_id=job_id, peptide_id=peptide_id)
                cur.execute(
                    """
                    INSERT INTO peptide_candidate (
                        peptide_id,
                        source_variant_id,
                        seq,
                        hla_allele,
                        binding_scores,
                        expression_tpm,
                        clonality,
                        features_vector
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
                    ON CONFLICT (peptide_id) DO UPDATE
                    SET source_variant_id = EXCLUDED.source_variant_id,
                        seq = EXCLUDED.seq,
                        hla_allele = EXCLUDED.hla_allele,
                        binding_scores = EXCLUDED.binding_scores,
                        expression_tpm = EXCLUDED.expression_tpm,
                        clonality = EXCLUDED.clonality,
                        features_vector = EXCLUDED.features_vector
                    """,
                    (
                        peptide_id,
                        source_variant_id,
                        peptide.get("peptide", ""),
                        peptide.get("hla_allele", "HLA-A*02:01"),
                        json.dumps({"binding_score": peptide.get("binding_score")}),
                        peptide.get("expression_tpm"),
                        peptide.get("clonality"),
                        json.dumps(feature_snapshot),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO prediction_record (
                        prediction_id,
                        peptide_id,
                        model_version,
                        score,
                        feature_snapshot,
                        pipeline_version,
                        image_digest,
                        parameters
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
                    ON CONFLICT (prediction_id) DO UPDATE
                    SET peptide_id = EXCLUDED.peptide_id,
                        model_version = EXCLUDED.model_version,
                        score = EXCLUDED.score,
                        feature_snapshot = EXCLUDED.feature_snapshot,
                        pipeline_version = EXCLUDED.pipeline_version,
                        image_digest = EXCLUDED.image_digest,
                        parameters = EXCLUDED.parameters
                    """,
                    (
                        prediction_id,
                        peptide_id,
                        model_version,
                        peptide.get("final_score", 0.0),
                        json.dumps(feature_snapshot),
                        pipeline_version,
                        image_digest,
                        json.dumps(parameters),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO provenance_record (
                        provenance_id,
                        entity_type,
                        entity_id,
                        dataset_id,
                        model_version,
                        pipeline_version,
                        image_digest,
                        parameters
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (provenance_id) DO UPDATE
                    SET entity_type = EXCLUDED.entity_type,
                        entity_id = EXCLUDED.entity_id,
                        dataset_id = EXCLUDED.dataset_id,
                        model_version = EXCLUDED.model_version,
                        pipeline_version = EXCLUDED.pipeline_version,
                        image_digest = EXCLUDED.image_digest,
                        parameters = EXCLUDED.parameters
                    """,
                    (
                        f"prov-{prediction_id}",
                        "prediction_record",
                        prediction_id,
                        metadata.get("dataset_id"),
                        model_version,
                        pipeline_version,
                        image_digest,
                        json.dumps(parameters),
                    ),
                )
        conn.commit()

    return {
        "enabled": True,
        "patient_id": patient_id,
        "sample_id": sample_id,
        "variants_persisted": len(variants),
        "sequence_runs_persisted": 1,
        "peptides_persisted": len(ranked),
        "predictions_persisted": len(ranked),
    }
