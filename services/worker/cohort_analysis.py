"""
Cohort-level neoantigen analysis for NeoAntigen-Studio.
Aggregates ranked_peptides results across multiple patients.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any


@dataclass
class CohortSummary:
    n_patients: int
    n_peptides_total: int
    n_unique_peptides: int
    median_binding_score: float
    median_final_score: float
    hla_frequency: dict[str, float]
    top_shared_peptides: list[dict]
    predictor_usage: dict[str, int]
    scores_partial_fraction: float
    per_patient_stats: list[dict]


def load_ranked_peptides(path: str | Path) -> list[dict]:
    """Carica ranked_peptides.json da un singolo job."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"ranked_peptides payload must be a list: {path}")
    return [dict(item) for item in payload]


def _infer_patient_id(path: str | Path) -> str:
    target = Path(path)
    if target.name == "ranked_peptides.json" and target.parent.name == "phase2":
        return target.parent.parent.name or target.stem
    return target.stem


def _patient_entries(
    ranked_peptides_files: list[str | Path],
    patient_ids: list[str] | None = None,
) -> list[tuple[str, list[dict]]]:
    if patient_ids is not None and len(patient_ids) != len(ranked_peptides_files):
        raise ValueError("patient_ids length must match ranked_peptides_files length")

    entries: list[tuple[str, list[dict]]] = []
    for index, path in enumerate(ranked_peptides_files):
        patient_id = patient_ids[index] if patient_ids is not None else _infer_patient_id(path)
        entries.append((patient_id, load_ranked_peptides(path)))
    return entries


def hla_frequency_table(
    ranked_peptides_files: list[str | Path],
) -> dict[str, float]:
    """
    Calcola la frequenza di ogni allele HLA nella coorte.
    La normalizzazione e' per osservazioni uniche allele-per-paziente, quindi la somma e' 1.0.
    """
    per_patient_observations: Counter[str] = Counter()
    for patient_id, ranked in _patient_entries(ranked_peptides_files):
        _ = patient_id
        patient_alleles = {str(item.get("hla_allele", "")).strip() for item in ranked if item.get("hla_allele")}
        for allele in patient_alleles:
            per_patient_observations[allele] += 1

    total = sum(per_patient_observations.values())
    if total == 0:
        return {}

    ordered = sorted(per_patient_observations.items(), key=lambda item: (-item[1], item[0]))
    return {allele: round(count / total, 6) for allele, count in ordered}


def shared_peptides(
    ranked_peptides_files: list[str | Path],
    min_patients: int = 2,
    min_final_score: float = 0.5,
) -> list[dict]:
    """
    Trova peptidi presenti in >= min_patients pazienti
    con final_score >= min_final_score.
    Utile per identificare neoantigeni candidati per vaccini universali.
    """
    peptide_hits: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for patient_id, ranked in _patient_entries(ranked_peptides_files):
        for item in ranked:
            peptide = str(item.get("peptide", "")).strip()
            if not peptide:
                continue
            final_score = float(item.get("final_score", 0.0) or 0.0)
            if final_score < min_final_score:
                continue
            current = peptide_hits[peptide].get(patient_id)
            if current is None or final_score > float(current.get("final_score", 0.0) or 0.0):
                peptide_hits[peptide][patient_id] = dict(item)

    shared: list[dict] = []
    for peptide, patient_map in peptide_hits.items():
        if len(patient_map) < min_patients:
            continue
        rows = list(patient_map.values())
        shared.append(
            {
                "peptide": peptide,
                "n_patients": len(patient_map),
                "patient_ids": sorted(patient_map.keys()),
                "max_final_score": round(max(float(r.get("final_score", 0.0) or 0.0) for r in rows), 4),
                "median_final_score": round(median(float(r.get("final_score", 0.0) or 0.0) for r in rows), 4),
                "hla_alleles": sorted({str(r.get("hla_allele", "")) for r in rows if r.get("hla_allele")}),
                "predictors": sorted({str(r.get("predictor_used", "")) for r in rows if r.get("predictor_used")}),
            }
        )

    return sorted(shared, key=lambda item: (-item["n_patients"], -item["max_final_score"], item["peptide"]))


def analyze_cohort(
    ranked_peptides_files: list[str | Path],
    patient_ids: list[str] | None = None,
) -> CohortSummary:
    """
    Aggrega i risultati di più pazienti.
    patient_ids: opzionale, se None usa il nome del file come ID.
    """
    entries = _patient_entries(ranked_peptides_files, patient_ids=patient_ids)
    all_rows = [row for _, ranked in entries for row in ranked]
    binding_scores = [float(row.get("binding_score", 0.0) or 0.0) for row in all_rows]
    final_scores = [float(row.get("final_score", 0.0) or 0.0) for row in all_rows]
    predictor_usage: Counter[str] = Counter()
    per_patient_stats: list[dict] = []
    unique_peptides: set[str] = set()
    partial_count = 0

    for patient_id, ranked in entries:
        patient_binding = [float(item.get("binding_score", 0.0) or 0.0) for item in ranked]
        patient_final = [float(item.get("final_score", 0.0) or 0.0) for item in ranked]
        patient_alleles = sorted({str(item.get("hla_allele", "")) for item in ranked if item.get("hla_allele")})
        patient_predictors = Counter(
            str(item.get("predictor_used", "unknown"))
            for item in ranked
            if item.get("predictor_used")
        )

        for item in ranked:
            peptide = str(item.get("peptide", "")).strip()
            if peptide:
                unique_peptides.add(peptide)
            predictor = str(item.get("predictor_used", "")).strip()
            if predictor:
                predictor_usage[predictor] += 1
            if bool(item.get("scores_are_partial")):
                partial_count += 1

        per_patient_stats.append(
            {
                "patient_id": patient_id,
                "n_peptides": len(ranked),
                "n_unique_peptides": len({str(item.get("peptide", "")).strip() for item in ranked if item.get("peptide")}),
                "median_binding_score": round(median(patient_binding), 4) if patient_binding else 0.0,
                "median_final_score": round(median(patient_final), 4) if patient_final else 0.0,
                "hla_alleles": patient_alleles,
                "predictor_usage": dict(patient_predictors),
            }
        )

    return CohortSummary(
        n_patients=len(entries),
        n_peptides_total=len(all_rows),
        n_unique_peptides=len(unique_peptides),
        median_binding_score=round(median(binding_scores), 4) if binding_scores else 0.0,
        median_final_score=round(median(final_scores), 4) if final_scores else 0.0,
        hla_frequency=hla_frequency_table(ranked_peptides_files),
        top_shared_peptides=shared_peptides(ranked_peptides_files),
        predictor_usage=dict(sorted(predictor_usage.items(), key=lambda item: (-item[1], item[0]))),
        scores_partial_fraction=round((partial_count / len(all_rows)), 4) if all_rows else 0.0,
        per_patient_stats=per_patient_stats,
    )


def export_cohort_csv(
    summary: CohortSummary,
    output_path: str | Path,
) -> None:
    """
    Esporta per_patient_stats come CSV per analisi esterne
    (R, Python pandas, Excel).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patient_id",
        "n_peptides",
        "n_unique_peptides",
        "median_binding_score",
        "median_final_score",
        "hla_alleles",
        "predictor_usage",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary.per_patient_stats:
            serialized = dict(row)
            serialized["hla_alleles"] = ";".join(row.get("hla_alleles", []))
            serialized["predictor_usage"] = json.dumps(row.get("predictor_usage", {}), sort_keys=True)
            writer.writerow(serialized)


def hla_heatmap_data(
    ranked_peptides_files: list[str | Path],
) -> dict:
    """
    Prepara i dati per una heatmap HLA x paziente.
    """
    entries = _patient_entries(ranked_peptides_files)
    patients = [patient_id for patient_id, _ in entries]
    allele_sets: list[set[str]] = []
    all_alleles: set[str] = set()
    for _, ranked in entries:
        alleles = {str(item.get("hla_allele", "")).strip() for item in ranked if item.get("hla_allele")}
        allele_sets.append(alleles)
        all_alleles.update(alleles)

    alleles = sorted(all_alleles)
    matrix = [[1 if allele in patient_alleles else 0 for allele in alleles] for patient_alleles in allele_sets]
    allele_counts = {allele: sum(row[index] for row in matrix) for index, allele in enumerate(alleles)}
    return {
        "alleles": alleles,
        "patients": patients,
        "matrix": matrix,
        "allele_counts": allele_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate ranked_peptides.json files across a cohort.")
    parser.add_argument("--inputs", required=True, help="Comma-separated ranked_peptides.json paths")
    parser.add_argument("--output-dir", required=True, help="Directory for cohort outputs")
    parser.add_argument("--min-patients", type=int, default=2)
    parser.add_argument("--min-score", type=float, default=0.5)
    args = parser.parse_args()

    inputs = [item.strip() for item in args.inputs.split(",") if item.strip()]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = analyze_cohort(inputs)
    heatmap = hla_heatmap_data(inputs)
    shared = shared_peptides(
        inputs,
        min_patients=args.min_patients,
        min_final_score=args.min_score,
    )

    (output_dir / "cohort_summary.json").write_text(
        json.dumps(asdict(summary), indent=2),
        encoding="utf-8",
    )
    (output_dir / "hla_heatmap.json").write_text(
        json.dumps(heatmap, indent=2),
        encoding="utf-8",
    )
    (output_dir / "shared_peptides.json").write_text(
        json.dumps(shared, indent=2),
        encoding="utf-8",
    )
    export_cohort_csv(summary, output_dir / "per_patient_stats.csv")


if __name__ == "__main__":
    main()
