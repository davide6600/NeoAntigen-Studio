from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

from services.worker.phase3_predictors import score_phase3_candidates
from services.api.job_store import get_job_store

_PIPELINE_VERSION = "phase3-v0.1"
_GENE_POOL = ["TP53", "KRAS", "EGFR", "BRAF", "PIK3CA", "PTEN", "NRAS", "ALK"]


def _read_local_inputs(input_paths: list[str]) -> list[bytes]:
    payloads: list[bytes] = []
    for raw_path in input_paths:
        path = Path(raw_path)
        if path.exists() and path.is_file():
            payloads.append(path.read_bytes())
    return payloads


def _seed_for_job(job_id: str, metadata: dict) -> int:
    digest = hashlib.sha256(f"{job_id}:{json.dumps(metadata, sort_keys=True)}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _build_reference_sequence(job_id: str, metadata: dict, payloads: list[bytes]) -> str:
    if payloads:
        merged = b"".join(payloads)
        tokens = [chr(b).upper() for b in merged if chr(b).upper() in {"A", "C", "G", "T"}]
        sequence = "".join(tokens)
        if len(sequence) >= 90:
            return sequence[:360]

    rng = random.Random(_seed_for_job(job_id, metadata))
    return "".join(rng.choice("ACGT") for _ in range(360))


def _gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    gc_count = sum(1 for base in sequence if base in {"G", "C"})
    return round(gc_count / len(sequence), 4)


def _generate_variants(sequence: str, seed: int) -> list[dict]:
    rng = random.Random(seed + 17)
    variants: list[dict] = []
    max_variants = min(8, max(3, len(sequence) // 60))
    for idx in range(max_variants):
        pos = 10 + (idx * 31)
        if pos >= len(sequence):
            break
        ref = sequence[pos]
        alt_choices = [b for b in "ACGT" if b != ref]
        alt = rng.choice(alt_choices)
        variants.append(
            {
                "variant_id": f"var-{idx + 1:03d}",
                "gene": _GENE_POOL[idx % len(_GENE_POOL)],
                "position": pos + 1,
                "ref": ref,
                "alt": alt,
                "effect": "missense_variant",
                "vaf": round(0.12 + (idx * 0.07), 3),
            }
        )
    return variants


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_synthetic_pipeline(*, job_id: str, metadata: dict, input_paths: list[str], outdir: Path) -> dict:
    job_store = get_job_store()
    existing_steps = {s["step_id"]: s for s in job_store.get_job_steps(job_id)}
    
    # helper to check for pause request
    def _should_pause(sid: str) -> bool:
        pause_steps = metadata.get("pause_after_steps", [])
        return sid in pause_steps

    seed = _seed_for_job(job_id, metadata)
    predictor_mode = os.getenv("NEOANTIGEN_PHASE3_PREDICTOR_MODE", "ensemble_seq2neo").strip().lower()

    # --- Step 1: Reference Indexing ---
    step_id = "step-indexing"
    if step_id in existing_steps and existing_steps[step_id]["status"] == "completed":
        sequence = existing_steps[step_id]["output_data"]["sequence"]
    else:
        job_store.add_job_step(job_id, step_id, "Reference Indexing", "running", {"input_paths": input_paths})
        payloads = _read_local_inputs(input_paths)
        sequence = _build_reference_sequence(job_id, metadata, payloads)
        output = {"sequence": sequence, "gc_fraction": _gc_fraction(sequence)}
        
        # Log sequences and calculations
        job_store.update_job_status(job_id, "running", f"Calculated reference sequence ({len(sequence)} bp, GC: {_gc_fraction(sequence):.2f})")
        if len(sequence) > 100:
            job_store.update_job_status(job_id, "running", f"Sequence bounds: {sequence[:50]}...{sequence[-50:]}")
        else:
            job_store.update_job_status(job_id, "running", f"Sequence: {sequence}")
            
        job_store.update_job_step(job_id, step_id, "completed", output)
        if _should_pause(step_id):
            job_store.update_job_step(job_id, step_id, "paused")
            job_store.update_job_status(job_id, "paused", f"Paused after {step_id} for human intervention")
            return {"status": "paused", "step_id": step_id}

    # --- Step 2: Variant Generation ---
    step_id = "step-variants"
    if step_id in existing_steps and existing_steps[step_id]["status"] == "completed":
        variants = existing_steps[step_id]["output_data"]["variants"]
    else:
        job_store.add_job_step(job_id, step_id, "Variant Generation", "running", {"base_sequence_len": len(sequence)})
        variants = _generate_variants(sequence, seed)
        output = {"variants": variants}
        
        # Log variants
        job_store.update_job_status(job_id, "running", f"Generated {len(variants)} potential variants using seed {seed}")
        for i, v in enumerate(variants[:5]):
            job_store.update_job_status(job_id, "running", f"Variant {i+1}: POS={v['position']} REF={v['ref']} ALT={v['alt']}")
        if len(variants) > 5:
            job_store.update_job_status(job_id, "running", f"... and {len(variants)-5} more variants")
            
        job_store.update_job_step(job_id, step_id, "completed", output)
        if _should_pause(step_id):
            job_store.update_job_step(job_id, step_id, "paused")
            job_store.update_job_status(job_id, "paused", f"Paused after {step_id} for human intervention")
            return {"status": "paused", "step_id": step_id}

    # --- Step 3: Peptide Scoring ---
    step_id = "step-scoring"
    if step_id in existing_steps and existing_steps[step_id]["status"] == "completed":
        ranked = existing_steps[step_id]["output_data"]["ranked"]
        features = existing_steps[step_id]["output_data"]["features"]
        predictor_summary = existing_steps[step_id]["output_data"]["predictor_summary"]
    else:
        job_store.add_job_step(job_id, step_id, "Peptide Scoring", "running", {"variant_count": len(variants)})
        ranked, features, predictor_summary = score_phase3_candidates(
            sequence=sequence,
            variants=variants,
            predictor_mode=predictor_mode,
        )
        output = {"ranked": ranked, "features": features, "predictor_summary": predictor_summary}
        
        # Log calculations
        top_score = ranked[0]['final_score'] if ranked else 0
        top_seq = ranked[0]['peptide'] if ranked else "N/A"
        job_store.update_job_status(job_id, "running", f"Scored peptides. Top candidate score: {top_score:.4f} ({top_seq})")
        job_store.update_job_status(job_id, "running", f"Predictor Engine ({predictor_mode}) summary: {json.dumps(predictor_summary)}")
        
        job_store.update_job_step(job_id, step_id, "completed", output)
        if _should_pause(step_id):
            job_store.update_job_step(job_id, step_id, "paused")
            job_store.update_job_status(job_id, "paused", f"Paused after {step_id} for human intervention")
            return {"status": "paused", "step_id": step_id}

    # Finalize outputs
    preprocessing = {
        "job_id": job_id,
        "pipeline_version": _PIPELINE_VERSION,
        "total_bases": len(sequence),
        "gc_fraction": _gc_fraction(sequence),
        "mode": "synthetic_only" if not input_paths else "synthetic_phase3",
    }
    if not input_paths:
        preprocessing["reads_processed"] = 0
        preprocessing["synthetic_reads_generated"] = len(variants)
    else:
        preprocessing["reads_processed"] = len(input_paths)
    files = {
        "preprocessing_qc_json": outdir / "preprocessing_metrics.json",
        "variant_annotations_json": outdir / "annotated_variants.json",
        "ranked_peptides_json": outdir / "ranked_peptides.json",
        "feature_table_json": outdir / "feature_table.json",
    }

    _write_json(files["preprocessing_qc_json"], preprocessing)
    _write_json(files["variant_annotations_json"], variants)
    _write_json(files["ranked_peptides_json"], ranked)
    _write_json(files["feature_table_json"], features)

    return {
        "engine": "synthetic",
        "pipeline_version": _PIPELINE_VERSION,
        "outputs": {artifact: str(path) for artifact, path in files.items()},
        "summary": {
            "variant_count": len(variants),
            "candidate_count": len(ranked),
            "predictor_mode": predictor_summary["predictor_mode"],
            "predictor_sources": predictor_summary["predictor_sources"],
            "top_candidate": ranked[0] if ranked else None,
        },
    }


def _run_nextflow_pipeline(*, job_id: str, metadata: dict, input_paths: list[str], outdir: Path) -> dict:
    manifest = {
        "job_id": job_id,
        "metadata": metadata,
        "input_paths": input_paths,
    }
    manifest_path = outdir / "input_manifest.json"
    _write_json(manifest_path, manifest)

    command = [
        "nextflow",
        "run",
        "pipelines/nextflow/main.nf",
        "--job_id",
        job_id,
        "--input_manifest",
        str(manifest_path),
        "--outdir",
        str(outdir),
    ]
    result = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Nextflow pipeline failed with code {result.returncode}: {result.stderr[:400]}")

    files = {
        "preprocessing_qc_json": outdir / "preprocessing_metrics.json",
        "variant_annotations_json": outdir / "annotated_variants.json",
        "ranked_peptides_json": outdir / "ranked_peptides.json",
        "feature_table_json": outdir / "feature_table.json",
    }
    for path in files.values():
        if not path.exists():
            raise RuntimeError(f"Nextflow pipeline did not produce expected output: {path}")

    ranked = json.loads(files["ranked_peptides_json"].read_text(encoding="utf-8"))

    return {
        "engine": "nextflow",
        "pipeline_version": _PIPELINE_VERSION,
        "outputs": {artifact: str(path) for artifact, path in files.items()},
        "summary": {
            "candidate_count": len(ranked),
            "top_candidate": ranked[0] if ranked else None,
        },
    }


def run_phase2_pipeline(*, job_id: str, metadata: dict, input_paths: list[str], output_root: str = "data/results") -> dict:
    outdir = Path(output_root) / job_id / "phase2"
    outdir.mkdir(parents=True, exist_ok=True)

    mode = os.getenv("NEOANTIGEN_PHASE2_ENGINE", "auto").strip().lower()
    if mode == "nextflow" and shutil.which("nextflow") is None:
        raise RuntimeError("NEOANTIGEN_PHASE2_ENGINE=nextflow but nextflow is not available")

    if mode in {"auto", "nextflow"} and shutil.which("nextflow") is not None:
        return _run_nextflow_pipeline(job_id=job_id, metadata=metadata, input_paths=input_paths, outdir=outdir)

    return _run_synthetic_pipeline(job_id=job_id, metadata=metadata, input_paths=input_paths, outdir=outdir)
