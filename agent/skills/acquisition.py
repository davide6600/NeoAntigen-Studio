from __future__ import annotations

import math
from dataclasses import dataclass


SKILL_METADATA = {
    "name": "acquisition_ranker",
    "capabilities": ["uncertainty_estimation", "acquisition_ranking", "batch_selection"],
    "input_types": ["PEPTIDE_FEATURES", "METRICS"],
    "priority": 75,
    "safety_level": "medium",
}


@dataclass
class PeptideEntry:
    peptide_id: str
    sequence: str
    score: float
    ensemble_predictions: list[float]


def compute_uncertainty(predictions: list[float]) -> float:
    """Shannon entropy of binary predictions as an uncertainty estimate.

    Returns a value in [0, ln(2)]; higher = more uncertain.
    """
    if not predictions:
        return 0.0
    p = max(0.0, min(1.0, sum(predictions) / len(predictions)))
    eps = 1e-9
    return -(p + eps) * math.log(p + eps) - (1.0 - p + eps) * math.log(1.0 - p + eps)


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    min_v, max_v = min(values), max(values)
    span = max_v - min_v
    if span == 0.0:
        return [0.5] * len(values)
    return [(v - min_v) / span for v in values]


def _jaccard_3mer(a: str, b: str) -> float:
    """Jaccard similarity on trigram sets as a fast sequence similarity proxy."""
    if len(a) < 3 or len(b) < 3:
        return float(a == b)
    kmers_a = {a[i : i + 3] for i in range(len(a) - 2)}
    kmers_b = {b[i : i + 3] for i in range(len(b) - 2)}
    union = len(kmers_a | kmers_b)
    return len(kmers_a & kmers_b) / union if union else 0.0


def compute_diversity_penalty(entry: PeptideEntry, selected: list[PeptideEntry]) -> float:
    """Diversity penalty in [0, 1]: 0 = unique relative to batch, 1 = identical to a member."""
    if not selected:
        return 0.0
    return max(_jaccard_3mer(entry.sequence, s.sequence) for s in selected)


def acquisition_score(
    normalized_score: float,
    normalized_uncertainty: float,
    diversity_penalty: float,
    alpha: float = 0.5,
    beta: float = 0.4,
    gamma: float = 0.1,
) -> float:
    """Weighted acquisition function: acq = α*score + β*uncertainty – γ*diversity_penalty."""
    return alpha * normalized_score + beta * normalized_uncertainty - gamma * diversity_penalty


def rank_batch(
    candidates: list[PeptideEntry],
    batch_size: int = 10,
    alpha: float = 0.5,
    beta: float = 0.4,
    gamma: float = 0.1,
) -> list[tuple[PeptideEntry, float]]:
    """Greedy batch selection maximising acquisition score with diversity enforcement."""
    if not candidates:
        return []

    uncertainties = [compute_uncertainty(c.ensemble_predictions) for c in candidates]
    scores = [c.score for c in candidates]
    norm_scores = _normalize(scores)
    norm_uncertainties = _normalize(uncertainties)

    selected: list[PeptideEntry] = []
    result: list[tuple[PeptideEntry, float]] = []
    remaining = list(zip(candidates, norm_scores, norm_uncertainties))

    while len(selected) < batch_size and remaining:
        best_idx = -1
        best_acq = -math.inf
        for i, (entry, ns, nu) in enumerate(remaining):
            dp = compute_diversity_penalty(entry, selected)
            acq = acquisition_score(ns, nu, dp, alpha, beta, gamma)
            if acq > best_acq:
                best_acq = acq
                best_idx = i

        chosen_entry, _, _ = remaining.pop(best_idx)
        selected.append(chosen_entry)
        result.append((chosen_entry, best_acq))

    return result

def run_acquisition(input_files: list[dict], metadata: dict | None = None) -> dict:
    """Mock acquisition step that validates files exist and returns metadata.
    If vcf_path is provided in metadata, parse it and extract peptides.
    """
    metadata = metadata or {}
    loaded = []
    for f in input_files:
        path = str(f.get("path", ""))
        loaded.append({
            "path": path,
            "type": f.get("artifact_type", "unknown")
        })
        
    vcf_path = metadata.get("vcf_path")
    peptides = []
    variants_found = 0
    if vcf_path:
        from agent.data.vcf_parser import parse_vcf, variants_to_peptides
        variants = parse_vcf(vcf_path)
        peptides = variants_to_peptides(variants)
        variants_found = len(variants)
        
    return {
        "files_loaded": loaded,
        "status": "ok",
        "count": len(loaded),
        "peptides": peptides,
        "variants_found": variants_found,
        "peptides_generated": len(peptides)
    }
