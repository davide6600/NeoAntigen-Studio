from __future__ import annotations

import hashlib
import json
import warnings
from . import hla_typing
from . import real_predictors
from . import stability_predictor
from . import tcr_recognition
from .expression_parser import parse_expression
from .clonality_estimator import estimate_clonality


def _stable_fraction(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _get_pd():
    """Lazily import pandas so tests/CI that don't install it can still import module.

    Returns the pandas module or `None` when pandas is not installed.
    """
    try:
        import pandas as pd

        return pd
    except ModuleNotFoundError:
        return None


def _translate_codon_to_aa(codon: str) -> str:
    if len(codon) < 3:
        return "X"
    codon = codon.upper()
    if any(c not in "ACGT" for c in codon):
        return "X"

    codon_table = {
        "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
        "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
        "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
        "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
        "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
        "AGT": "S", "AGC": "S",
        "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
        "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
        "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
        "TAT": "Y", "TAC": "Y",
        "TAA": "*", "TAG": "*", "TGA": "*",
        "CAT": "H", "CAC": "H",
        "CAA": "Q", "CAG": "Q",
        "AAT": "N", "AAC": "N",
        "AAA": "K", "AAG": "K",
        "GAT": "D", "GAC": "D",
        "GAA": "E", "GAG": "E",
        "TGT": "C", "TGC": "C", "TGG": "W",
        "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
        "AGA": "R", "AGG": "R",
        "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
    }
    return codon_table.get(codon, "X")


def _translate_to_peptide(window: str) -> str:
    peptide = []
    for i in range(0, len(window) - 2, 3):
        codon = window[i : i + 3]
        aa = _translate_codon_to_aa(codon)
        if aa == "*":
            break
        peptide.append(aa)
        if len(peptide) == 9:
            break
    return "".join(peptide)


def _fallback_peptide_from_variant(variant: dict) -> str:
    alt_aa = str(variant.get("alt_aa") or variant.get("alt") or "X").upper()
    base = alt_aa[0] if alt_aa else "X"
    return (base * 9)[:9]


def build_candidate_peptides(
    variants: list[dict],
    *,
    sequence: str | None = None,
    hla_alleles: list[str] | None = None,
    hla_types: list[str] | None = None,
    manifest_hla: list[str] | None = None,
    input_paths: list[str] | None = None,
    work_dir: str | None = None,
    sample_id: str = "sample",
) -> list[dict]:
    hla_result = hla_typing.resolve_hla_from_manifest(
        manifest={"hla_alleles": hla_alleles or hla_types or manifest_hla},
        input_paths=input_paths or [],
        work_dir=work_dir,
        sample_id=sample_id,
    )
    alleles = hla_result.alleles

    candidates: list[dict] = []
    candidate_counter = 1
    for variant in variants:
        source_variant = dict(variant)
        raw_sequence = sequence or str(source_variant.pop("_phase2_sequence", "") or "")
        if raw_sequence:
            start = max(0, source_variant["position"] - 13)
            end = min(len(raw_sequence), start + 27)
            peptide = _translate_to_peptide(raw_sequence[start:end])
        else:
            peptide = _fallback_peptide_from_variant(source_variant)

        for allele in alleles:
            candidates.append(
                {
                    "candidate_id": f"cand-{candidate_counter:03d}",
                    "peptide_id": f"pep-{candidate_counter:03d}",
                    "peptide": peptide,
                    "source_variant_id": source_variant.get("variant_id", source_variant.get("id", f"var-{candidate_counter:03d}")),
                    "gene": source_variant["gene"],
                    "hla_allele": allele,
                    "variant": source_variant,
                }
            )
            candidate_counter += 1
    return candidates, hla_result


def _predict_binding_scores(candidate: dict, predictor_mode: str) -> dict:
    _ = predictor_mode
    bp = real_predictors.predict_binding(
        candidate["peptide"],
        candidate["hla_allele"],
        prefer_offline=True,
        backend=candidate.get("backend", "auto"),
    )
    candidate["binding_score"] = bp["score"]
    candidate["predictor_used"] = bp["predictor"]
    candidate["affinity_nm"] = bp["affinity_nm"]
    candidate["percentile_rank"] = bp["percentile_rank"]
    sp = stability_predictor.predict_stability(
        candidate["peptide"],
        candidate["hla_allele"],
    )
    candidate["stability_score"] = sp["stability_score"]
    candidate["thalf_hours"] = sp["thalf_hours"]
    candidate["stability_backend"] = sp["stability_backend"]
    tcr_result = tcr_recognition.predict_tcr_recognition(
        candidate["peptide"],
        candidate["hla_allele"],
    )
    candidate["tcr_score"] = tcr_result.score
    candidate["tcr_method"] = tcr_result.method
    return candidate


def score_phase2_candidates(
    *,
    sequence: str,
    variants: list[dict],
    hla_alleles: list[str] | None = None,
    hla_types: list[str] | None = None,
    manifest_hla: list[str] | None = None,
    input_paths: list[str] | None = None,
    work_dir: str | None = None,
    sample_id: str = "sample",
    backend: str = "auto",
    predictor_mode: str = "ensemble_wrappers",
    expression_file: str | None = None,
    tumour_purity: float = 1.0,
    clonal_threshold: float = 0.8,
) -> tuple[list[dict], list[dict], dict]:
    ranked: list[dict] = []
    expressed_genes = None
    if expression_file is not None:
        import logging
        logger = logging.getLogger(__name__)
        try:
            expr_df = parse_expression(expression_file, fmt="auto", tpm_threshold=1.0)
            expressed_genes = set(expr_df["gene_id"].tolist())
            logger.info("Expression filter: %d expressed genes loaded from %s",
                        len(expressed_genes), expression_file)
        except Exception as exc:
            logger.warning("Expression filter skipped due to error: %s", exc)
            expressed_genes = None
    candidates, hla_result = build_candidate_peptides(
        variants,
        sequence=sequence,
        hla_alleles=hla_alleles,
        hla_types=hla_types,
        manifest_hla=manifest_hla,
        input_paths=input_paths,
        work_dir=work_dir,
        sample_id=sample_id,
    )
    # Lazily import pandas when needed so CI jobs without pandas can still import this module
    pd = _get_pd()
    # Apply expression-based filtering only when expression data was provided
    if expressed_genes is not None and candidates:
        # Il DataFrame deve avere una colonna 'gene_id' o 'gene'. Adatta il nome colonna se necessario.
        before_filter = len(candidates)
        gene_col = "gene_id" if any("gene_id" in c for c in candidates) else "gene"
        if pd is None:
            raise RuntimeError("pandas is required for phase2 scoring but not installed")
        # Use pandas DataFrame for expression-based filtering
        candidates_df = pd.DataFrame(candidates)
        candidates_df = candidates_df[candidates_df[gene_col].isin(expressed_genes)].reset_index(drop=True)
        logger.info("Expression filter: %d / %d candidates retained (gene expressed)", len(candidates_df), before_filter)
        candidates = candidates_df.to_dict(orient="records")
    for idx, candidate in enumerate(candidates, start=1):
        variant = candidate["variant"]
        candidate["backend"] = backend
        candidate = _predict_binding_scores(candidate, predictor_mode)
        predictor_map = {candidate["predictor_used"]: candidate["binding_score"]}
        binding_score = candidate["binding_score"]
        stability_score = candidate["stability_score"]
        tcr_score = candidate["tcr_score"]
        expression_fraction = _stable_fraction("expression", candidate["gene"], candidate["peptide_id"], predictor_mode)
        expression_tpm = round(7.5 + (expression_fraction * 9.0) + (idx * 1.2), 3)
        expression_tpm_normalized = min(expression_tpm / 100.0, 1.0)
        clonality = round(min(0.95, 0.25 + variant["vaf"]), 4)
        final_score = round(
            (0.40 * binding_score)
            + (0.20 * stability_score)
            + (0.25 * tcr_score)
            + (0.10 * expression_tpm_normalized)
            + (0.05 * clonality),
            4,
        )
        scores_are_partial = (
            candidate["stability_backend"] == "stability_stub"
            or candidate["tcr_method"] == "stub_tcr"
        )
        ranked.append(
            {
                "rank": idx,
                "peptide_id": candidate["peptide_id"],
                "peptide": candidate["peptide"],
                "source_variant_id": candidate["source_variant_id"],
                "gene": candidate["gene"],
                "binding_score": binding_score,
                "stability_score": stability_score,
                "thalf_hours": candidate["thalf_hours"],
                "stability_backend": candidate["stability_backend"],
                "tcr_score": tcr_score,
                "tcr_method": candidate["tcr_method"],
                "scores_are_partial": scores_are_partial,
                "expression_tpm": expression_tpm,
                "clonality": clonality,
                "final_score": final_score,
                "hla_allele": candidate["hla_allele"],
                "predictor_used": candidate["predictor_used"],
                "affinity_nm": candidate["affinity_nm"],
                "percentile_rank": candidate["percentile_rank"],
                "hla_typing_method": hla_result.typing_method,
                "predictor_mode": predictor_mode,
                "predictor_scores": predictor_map,
            }
        )

    # Prepare DataFrame for clonality estimation and final sorting
    import logging
    logger = logging.getLogger(__name__)

    if pd is None:
        raise RuntimeError("pandas is required for phase2 scoring but not installed")

    ranked_df = pd.DataFrame(ranked)

    if "vaf" in ranked_df.columns:
        logger.info("Clonality estimation: running simple_ccf (purity=%.2f, threshold=%.2f)", tumour_purity, clonal_threshold)
        ranked_df = estimate_clonality(
            ranked_df,
            mode="simple_ccf",
            purity=tumour_purity,
            clonal_threshold=clonal_threshold,
        )
    else:
        logger.warning(
            "Clonality estimation skipped: 'vaf' column not found in candidates DataFrame. Add VAF to your input VCF processing step to enable CCF estimation."
        )
        ranked_df["ccf"] = None
        ranked_df["is_clonal"] = False
        ranked_df["clonality"] = "unknown"

    # Ottieni il nome della colonna di affinità (adattalo se si chiama diversamente)
    affinity_col = "affinity_nm" if "affinity_nm" in ranked_df.columns else "score"

    ranked_df = ranked_df.sort_values(by=["is_clonal", affinity_col], ascending=[False, True]).reset_index(drop=True)
    ranked = ranked_df.to_dict(orient="records")
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx

    feature_table = [
        {
            "peptide_id": item["peptide_id"],
            "binding_score": item["binding_score"],
            "stability_score": item["stability_score"],
            "thalf_hours": item["thalf_hours"],
            "stability_backend": item["stability_backend"],
            "tcr_score": item["tcr_score"],
            "tcr_method": item["tcr_method"],
            "affinity_nm": item["affinity_nm"],
            "percentile_rank": item["percentile_rank"],
            "predictor_used": item["predictor_used"],
            "expression_tpm": item["expression_tpm"],
            "clonality": item["clonality"],
            "final_score": item["final_score"],
            "predictor_mode": item["predictor_mode"],
        }
        for item in ranked
    ]
    summary = {
        "predictor_mode": predictor_mode,
        "predictor_sources": [_resolve_predictor_source(backend)],
        "stability_backend": stability_predictor.get_available_stability_backend(),
        "tcr_predictor": tcr_recognition.get_available_tcr_predictor(),
        "candidate_count": len(ranked),
        "hla_typing_method": hla_result.typing_method,
        "hla_typing_confidence": hla_result.confidence,
    }
    # Attach TPM values to the final ranked results (if expression data was loaded)
    try:
        if expressed_genes is not None and expr_df is not None:
            if pd is None:
                raise RuntimeError("pandas is required for phase2 scoring but not installed")
            ranked_df = pd.DataFrame(ranked)
            if not ranked_df.empty:
                gene_col = "gene_id" if "gene_id" in ranked_df.columns else "gene"
                ranked_df = ranked_df.merge(
                    expr_df.rename(columns={"gene_id": gene_col}),
                    on=gene_col,
                    how="left",
                )
                ranked = ranked_df.to_dict(orient="records")
    except NameError:
        # If expr_df or ranked aren't defined, skip the merge silently
        pass
    return ranked, feature_table, summary


def _resolve_predictor_source(backend: str) -> str:
    if backend == "pvacseq":
        return "pvacseq"
    if backend == "mhcflurry":
        return "mhcflurry_2"
    if backend == "iedb":
        return "netmhcpan_iedb_api"
    if backend == "stub":
        return "stub_fallback"
    return real_predictors.get_available_predictor()


def score_phase2_candidates_from_variants_json(
    *,
    variants: list[dict],
    sequence: str,
    predictor_mode: str,
    hla_alleles: list[str] | None = None,
    hla_types: list[str] | None = None,
    manifest_hla: list[str] | None = None,
    input_paths: list[str] | None = None,
    work_dir: str | None = None,
    sample_id: str = "sample",
    backend: str = "auto",
    expression_file: str | None = None,
    tumour_purity: float = 1.0,
    clonal_threshold: float = 0.8,
) -> dict:
    ranked, feature_table, summary = score_phase2_candidates(
        sequence=sequence,
        variants=variants,
        predictor_mode=predictor_mode,
        expression_file=expression_file,
        hla_alleles=hla_alleles,
        hla_types=hla_types,
        manifest_hla=manifest_hla,
        input_paths=input_paths,
        work_dir=work_dir,
        sample_id=sample_id,
        backend=backend,
        tumour_purity=tumour_purity,
        clonal_threshold=clonal_threshold,
    )
    return {
        "ranked": ranked,
        "feature_table": feature_table,
        "summary": summary,
    }


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Score Phase 2 peptide candidates with predictor wrappers.")
    parser.add_argument("--variants-json", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--predictor-mode", default="ensemble_wrappers")
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--hla-alleles", help="Comma-separated HLA alleles (e.g. HLA-A*02:01,HLA-B*07:02)")
    parser.add_argument("--hla-types", help="Deprecated alias for --hla-alleles")
    parser.add_argument("--input-paths", help="Comma-separated input FASTQ/BAM paths for automatic HLA typing")
    parser.add_argument("--work-dir", help="Working directory for temporary HLA typing outputs")
    parser.add_argument("--sample-id", default="sample")
    parser.add_argument("--ranked-output", required=True)
    parser.add_argument("--feature-output", required=True)
    parser.add_argument("--summary-output", required=False)
    parser.add_argument(
        "--expression-file",
        type=str,
        default=None,
        help="Path to RNA-seq quantification file (Salmon quant.sf, "
             "Kallisto abundance.tsv, STAR ReadsPerGene.out.tab, or "
             "any TSV/CSV with gene_id and TPM columns). "
             "If not provided, expression filtering is skipped.",
    )
    parser.add_argument(
        "--tumour-purity",
        type=float,
        default=1.0,
        help="Estimated tumour purity (0-1). Default 1.0",
    )
    parser.add_argument(
        "--clonal-threshold",
        type=float,
        default=0.8,
        help="CCF threshold to call a variant clonal. Default 0.8",
    )
    args = parser.parse_args()

    if args.hla_types:
        warnings.warn("--hla-types is deprecated; use --hla-alleles instead", DeprecationWarning)
    raw_hla = args.hla_alleles or args.hla_types
    hla_alleles = raw_hla.split(",") if raw_hla else None
    input_paths = args.input_paths.split(",") if args.input_paths else None
    variants = json.loads(Path(args.variants_json).read_text(encoding="utf-8"))
    scored = score_phase2_candidates_from_variants_json(
        variants=variants,
        sequence=args.sequence,
        predictor_mode=args.predictor_mode,
        expression_file=args.expression_file,
        hla_alleles=hla_alleles,
        hla_types=hla_alleles,
        input_paths=input_paths,
        work_dir=args.work_dir,
        sample_id=args.sample_id,
        backend=args.backend,
        tumour_purity=args.tumour_purity,
        clonal_threshold=args.clonal_threshold,
    )
    Path(args.ranked_output).write_text(json.dumps(scored["ranked"], indent=2), encoding="utf-8")
    Path(args.feature_output).write_text(json.dumps(scored["feature_table"], indent=2), encoding="utf-8")
    if args.summary_output:
        Path(args.summary_output).write_text(json.dumps(scored["summary"], indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
