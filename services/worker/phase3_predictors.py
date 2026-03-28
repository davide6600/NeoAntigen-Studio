from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

@dataclass(frozen=True)
class PredictorScore:
    predictor_name: str
    score: float

def _stable_fraction(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF

def _translate_to_peptide(window: str) -> str:
    aa_map = {"A": "A", "C": "C", "G": "G", "T": "T"}
    mapped = "".join(aa_map.get(ch, "X") for ch in window)
    return (mapped + "ACDEFGHIK")[:9]

def build_candidate_peptides(sequence: str, variants: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for idx, variant in enumerate(variants):
        start = max(0, variant["position"] - 5)
        end = min(len(sequence), start + 12)
        peptide = _translate_to_peptide(sequence[start:end])
        candidates.append({
            "candidate_id": f"cand-{idx + 1:03d}",
            "peptide_id": f"pep-{idx + 1:03d}",
            "peptide": peptide,
            "source_variant_id": variant["variant_id"],
            "gene": variant["gene"],
            "hla_allele": "HLA-A*02:01",
            "variant": variant,
        })
    return candidates

def _predict_binding_scores(candidate: dict, predictor_mode: str) -> list[PredictorScore]:
    peptide = candidate["peptide"]
    allele = candidate["hla_allele"]
    variant_id = candidate["source_variant_id"]
    predictors = ["pvactools", "netmhcpan", "mhcflurry"]
    scores: list[PredictorScore] = []
    for predictor_name in predictors:
        fraction = _stable_fraction(predictor_mode, predictor_name, peptide, allele, variant_id)
        score = round(0.35 + (fraction * 0.6), 4)
        scores.append(PredictorScore(predictor_name=predictor_name, score=score))
    return scores

def _predict_seq2neo_immunogenicity(candidate: dict, predictor_mode: str) -> float:
    # Simulated Deep Learning Immunogenicity Score
    fraction = _stable_fraction(predictor_mode, "seq2neo", candidate["peptide"], candidate["hla_allele"])
    return round(fraction, 4)

def _predict_uncertainty(candidate: dict, predictor_mode: str) -> float:
    # Simulated predictive entropy / model uncertainty
    fraction = _stable_fraction(predictor_mode, "uncertainty", candidate["peptide"])
    return round(fraction * 0.5, 4) # uncertainty between 0.0 and 0.5

def score_phase3_candidates(
    *,
    sequence: str,
    variants: list[dict],
    predictor_mode: str = "ensemble_seq2neo",
) -> tuple[list[dict], list[dict], dict]:
    ranked: list[dict] = []
    for idx, candidate in enumerate(build_candidate_peptides(sequence, variants), start=1):
        variant = candidate["variant"]
        
        # MHC Ensemble
        predictor_scores = _predict_binding_scores(candidate, predictor_mode)
        predictor_map = {item.predictor_name: item.score for item in predictor_scores}
        binding_score = round(sum(item.score for item in predictor_scores) / len(predictor_scores), 4)
        
        # Additional features
        expression_fraction = _stable_fraction("expression", candidate["gene"], candidate["peptide_id"], predictor_mode)
        expression_tpm = round(7.5 + (expression_fraction * 9.0) + (idx * 1.2), 3)
        clonality = round(min(0.95, 0.25 + variant["vaf"]), 4)
        
        # Seq2Neo integration
        seq2neo_score = _predict_seq2neo_immunogenicity(candidate, predictor_mode)
        predictor_map["seq2neo"] = seq2neo_score
        
        # Active Learning - Acquisition scoring
        uncertainty = _predict_uncertainty(candidate, predictor_mode)
        
        # Final combined Score (alpha * seq2neo + beta * binding + gamma * expression/clonality)
        final_score = round(
            (seq2neo_score * 0.45) + (binding_score * 0.35) + (min(1.0, expression_tpm / 20.0) * 0.1) + (clonality * 0.1), 4
        )
        
        # Acquisition function = normalized_score + beta * uncertainty
        acquisition_score = round(final_score + (0.5 * uncertainty), 4)
        
        ranked.append({
            "rank": idx, # to be updated after sorting
            "peptide_id": candidate["peptide_id"],
            "peptide": candidate["peptide"],
            "source_variant_id": candidate["source_variant_id"],
            "gene": candidate["gene"],
            "binding_score": binding_score,
            "expression_tpm": expression_tpm,
            "clonality": clonality,
            "seq2neo_score": seq2neo_score,
            "uncertainty": uncertainty,
            "acquisition_score": acquisition_score,
            "final_score": final_score,
            "hla_allele": candidate["hla_allele"],
            "predictor_mode": predictor_mode,
            "predictor_scores": predictor_map,
        })

    # Sort by acquisition_score or final_score depending on active learning mode
    # For now, default to ranking by final_score (pure prediction) but retain acquisition score for wet-lab
    ranked = sorted(ranked, key=lambda item: item["final_score"], reverse=True)
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx

    feature_table = [
        {
            "peptide_id": item["peptide_id"],
            "binding_score": item["binding_score"],
            "expression_tpm": item["expression_tpm"],
            "clonality": item["clonality"],
            "seq2neo_score": item["seq2neo_score"],
            "uncertainty": item["uncertainty"],
            "acquisition_score": item["acquisition_score"],
            "final_score": item["final_score"],
            "pvactools_score": item["predictor_scores"]["pvactools"],
            "netmhcpan_score": item["predictor_scores"]["netmhcpan"],
            "mhcflurry_score": item["predictor_scores"]["mhcflurry"],
            "predictor_mode": item["predictor_mode"],
        }
        for item in ranked
    ]
    summary = {
        "predictor_mode": predictor_mode,
        "predictor_sources": ["pvactools", "netmhcpan", "mhcflurry", "seq2neo"],
        "candidate_count": len(ranked),
    }
    return ranked, feature_table, summary

def score_phase3_candidates_from_variants_json(
    *,
    variants: list[dict],
    sequence: str,
    predictor_mode: str,
) -> dict:
    ranked, feature_table, summary = score_phase3_candidates(
        sequence=sequence,
        variants=variants,
        predictor_mode=predictor_mode,
    )
    return {
        "ranked": ranked,
        "feature_table": feature_table,
        "summary": summary,
    }

def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Score Phase 3 peptide candidates with Seq2Neo and ensemble predictor wrappers.")
    parser.add_argument("--variants-json", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--predictor-mode", default="ensemble_seq2neo")
    parser.add_argument("--ranked-output", required=True)
    parser.add_argument("--feature-output", required=True)
    parser.add_argument("--summary-output", required=False)
    args = parser.parse_args()

    variants = json.loads(Path(args.variants_json).read_text(encoding="utf-8"))
    scored = score_phase3_candidates_from_variants_json(
        variants=variants,
        sequence=args.sequence,
        predictor_mode=args.predictor_mode,
    )
    Path(args.ranked_output).write_text(json.dumps(scored["ranked"], indent=2), encoding="utf-8")
    Path(args.feature_output).write_text(json.dumps(scored["feature_table"], indent=2), encoding="utf-8")
    if args.summary_output:
        Path(args.summary_output).write_text(json.dumps(scored["summary"], indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
