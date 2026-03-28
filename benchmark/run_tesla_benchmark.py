#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.worker import real_predictors

DEFAULT_DATASET_PATH = Path(__file__).with_name("tesla_validated.csv")
DEFAULT_CACHE_PATH = Path(__file__).with_name("cache.json")
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "results" / "tesla_report.json"
REQUIRED_COLUMNS = {
    "patient_id",
    "peptide",
    "hla_allele",
    "immunogenic",
}


def load_tesla_dataset(path: str | Path) -> list[dict]:
    dataset_path = Path(path)
    rows: list[dict] = []
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        if not REQUIRED_COLUMNS.issubset(fieldnames):
            raise ValueError(
                "TESLA dataset must contain columns: "
                + ", ".join(sorted(REQUIRED_COLUMNS))
            )
        for row in reader:
            rows.append(
                {
                    "patient_id": str(row["patient_id"]).strip(),
                    "peptide": str(row["peptide"]).strip(),
                    "hla_allele": str(row["hla_allele"]).strip(),
                    "immunogenic": int(str(row["immunogenic"]).strip()),
                    "source": str(row.get("source", "legacy_input")).strip() or "legacy_input",
                }
            )
    return rows


def load_cache(path: str | Path) -> dict[str, dict]:
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def save_cache(path: str | Path, cache: dict[str, dict]) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def cache_key(peptide: str, allele: str) -> str:
    return f"{peptide}|{allele}"


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _sanitize_binding_result(result: dict) -> dict:
    return {
        "score": float(result.get("score", 0.0)),
        "affinity_nm": _safe_float(result.get("affinity_nm")),
        "percentile_rank": _safe_float(result.get("percentile_rank")),
        "predictor": str(result.get("predictor", "unknown")),
    }


def get_cached_or_predict(
    peptide: str,
    allele: str,
    cache: dict[str, dict],
    cache_path: str | Path,
    *,
    predictor_fn=None,
    sleep_seconds: float = 1.0,
) -> tuple[dict, bool]:
    key = cache_key(peptide, allele)
    cached = cache.get(key)
    if cached is not None:
        return _sanitize_binding_result(cached), True

    predictor = predictor_fn or real_predictors.predict_binding
    try:
        raw_result = predictor(peptide, allele, prefer_offline=False)
    except TypeError:
        raw_result = predictor(peptide, allele)
    result = _sanitize_binding_result(raw_result)
    cache[key] = result
    save_cache(cache_path, cache)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return result, False


def _rank_values(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        next_cursor = cursor + 1
        while next_cursor < len(indexed) and indexed[next_cursor][1] == indexed[cursor][1]:
            next_cursor += 1
        average_rank = (cursor + 1 + next_cursor) / 2.0
        for original_index, _ in indexed[cursor:next_cursor]:
            ranks[original_index] = average_rank
        cursor = next_cursor
    return ranks


def _pearson_correlation(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return 0.0
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    centered_x = [value - mean_x for value in x_values]
    centered_y = [value - mean_y for value in y_values]
    numerator = sum(x * y for x, y in zip(centered_x, centered_y))
    denom_x = math.sqrt(sum(value * value for value in centered_x))
    denom_y = math.sqrt(sum(value * value for value in centered_y))
    if denom_x == 0.0 or denom_y == 0.0:
        return 0.0
    return numerator / (denom_x * denom_y)


def spearman_correlation(
    scores: list[float],
    labels: list[int],
    *,
    permutations: int = 5000,
    seed: int = 0,
) -> tuple[float, float]:
    if len(scores) != len(labels) or len(scores) < 2:
        return 0.0, 1.0

    score_ranks = _rank_values(scores)
    label_ranks = _rank_values([float(label) for label in labels])
    observed = _pearson_correlation(score_ranks, label_ranks)

    if permutations <= 0:
        return observed, 1.0

    rng = random.Random(seed)
    extreme = 0
    shuffled = list(label_ranks)
    for _ in range(permutations):
        rng.shuffle(shuffled)
        permuted = _pearson_correlation(score_ranks, shuffled)
        if abs(permuted) >= abs(observed):
            extreme += 1
    p_value = (extreme + 1) / (permutations + 1)
    return observed, p_value


def _auc_roc(labels: list[int], scores: list[float]) -> float:
    positives = [score for label, score in zip(labels, scores) if label == 1]
    negatives = [score for label, score in zip(labels, scores) if label == 0]
    if not positives or not negatives:
        return 0.0

    wins = 0.0
    for positive_score in positives:
        for negative_score in negatives:
            if positive_score > negative_score:
                wins += 1.0
            elif positive_score == negative_score:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _auc_pr(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    if positives == 0:
        return 0.0

    paired = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    true_positives = 0
    false_positives = 0
    previous_recall = 0.0
    average_precision = 0.0

    for _, label in paired:
        if label == 1:
            true_positives += 1
        else:
            false_positives += 1
        recall = true_positives / positives
        precision = true_positives / (true_positives + false_positives)
        average_precision += (recall - previous_recall) * precision
        previous_recall = recall
    return average_precision


def calculate_metrics(
    per_peptide: list[dict],
    *,
    spearman_permutations: int = 5000,
) -> dict[str, float | dict[str, float]]:
    labels = [int(item["immunogenic"]) for item in per_peptide]
    scores = [float(item["binding_score"]) for item in per_peptide]
    predictions = [
        item["affinity_nm"] is not None and float(item["affinity_nm"]) < 500.0
        for item in per_peptide
    ]

    true_positives = sum(1 for label, prediction in zip(labels, predictions) if label == 1 and prediction)
    false_positives = sum(1 for label, prediction in zip(labels, predictions) if label == 0 and prediction)
    false_negatives = sum(1 for label, prediction in zip(labels, predictions) if label == 1 and not prediction)

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    spearman_r, spearman_p = spearman_correlation(
        scores,
        labels,
        permutations=spearman_permutations,
    )

    return {
        "auc_roc": _auc_roc(labels, scores),
        "auc_pr": _auc_pr(labels, scores),
        "spearman_r": spearman_r,
        "spearman_p": spearman_p,
        "threshold_500nm": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
    }


def run_benchmark(
    *,
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    predictor_fn=None,
    sleep_seconds: float = 1.0,
    spearman_permutations: int = 5000,
    save_report: bool = True,
) -> dict:
    dataset = load_tesla_dataset(dataset_path)
    cache = load_cache(cache_path)
    per_peptide: list[dict] = []

    for row in dataset:
        result, cache_hit = get_cached_or_predict(
            row["peptide"],
            row["hla_allele"],
            cache,
            cache_path,
            predictor_fn=predictor_fn,
            sleep_seconds=sleep_seconds,
        )
        affinity_nm = result["affinity_nm"]
        per_peptide.append(
            {
                **row,
                "binding_score": result["score"],
                "affinity_nm": affinity_nm,
                "percentile_rank": result["percentile_rank"],
                "predicted_binder_500nm": affinity_nm is not None and affinity_nm < 500.0,
                "predictor_used": result["predictor"],
                "cache_hit": cache_hit,
            }
        )

    metrics = calculate_metrics(
        per_peptide,
        spearman_permutations=spearman_permutations,
    )
    predictors = sorted({entry["predictor_used"] for entry in per_peptide})
    predictor_used = predictors[0] if len(predictors) == 1 else "mixed"

    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "predictor_used": predictor_used,
        "n_peptides": len(per_peptide),
        "n_immunogenic": sum(entry["immunogenic"] for entry in per_peptide),
        "n_non_immunogenic": sum(1 for entry in per_peptide if entry["immunogenic"] == 0),
        "auc_roc": round(float(metrics["auc_roc"]), 6),
        "auc_pr": round(float(metrics["auc_pr"]), 6),
        "spearman_r": round(float(metrics["spearman_r"]), 6),
        "spearman_p": round(float(metrics["spearman_p"]), 6),
        "threshold_500nm": {
            "precision": round(float(metrics["threshold_500nm"]["precision"]), 6),
            "recall": round(float(metrics["threshold_500nm"]["recall"]), 6),
            "f1": round(float(metrics["threshold_500nm"]["f1"]), 6),
        },
        "per_peptide": per_peptide,
    }

    if save_report:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def print_report(report: dict) -> None:
    print("=" * 60)
    print("NeoAntigen-Studio TESLA Benchmark")
    print("=" * 60)
    print(f"Predictor used: {report['predictor_used']}")
    print(
        f"Peptides: {report['n_peptides']} total "
        f"({report['n_immunogenic']} immunogenic / {report['n_non_immunogenic']} non-immunogenic)"
    )
    print(f"AUC-ROC: {report['auc_roc']:.6f}")
    print(f"AUC-PR: {report['auc_pr']:.6f}")
    print(
        f"Spearman r: {report['spearman_r']:.6f} "
        f"(p={report['spearman_p']:.6f})"
    )
    print("Threshold IC50 < 500 nM:")
    print(f"  Precision: {report['threshold_500nm']['precision']:.6f}")
    print(f"  Recall:    {report['threshold_500nm']['recall']:.6f}")
    print(f"  F1:        {report['threshold_500nm']['f1']:.6f}")
    print("")
    print("Per peptide:")
    for item in report["per_peptide"]:
        affinity = "NA" if item["affinity_nm"] is None else f"{item['affinity_nm']:.2f}"
        percentile = (
            "NA"
            if item["percentile_rank"] is None
            else f"{float(item['percentile_rank']):.2f}"
        )
        cache_state = "cache" if item["cache_hit"] else "api"
        print(
            f"- {item['patient_id']}: {item['peptide']} / {item['hla_allele']} "
            f"immunogenic={item['immunogenic']} "
            f"score={item['binding_score']:.4f} "
            f"IC50={affinity}nM "
            f"percentile={percentile} "
            f"predictor={item['predictor_used']} "
            f"source={cache_state}"
        )


def _have_mhcflurry() -> bool:
    try:
        from mhcflurry import Class1PresentationPredictor

        Class1PresentationPredictor.load()
        return True
    except Exception:
        return False


def _build_predictor_fn(name: str):
    if name == "iedb":
        return lambda peptide, allele, prefer_offline=False: real_predictors.predict_binding(
            peptide,
            allele,
            prefer_offline=False,
            backend="iedb",
        )
    if name == "mhcflurry":
        return lambda peptide, allele, prefer_offline=False: real_predictors.predict_binding(
            peptide,
            allele,
            prefer_offline=True,
            backend="mhcflurry",
        )
    if name == "stub":
        return lambda peptide, allele, prefer_offline=False: real_predictors.predict_binding(
            peptide,
            allele,
            prefer_offline=False,
            backend="stub",
        )
    return None


def _run_legacy_cli(args: argparse.Namespace) -> int:
    dataset_path = args.tesla_data or args.dataset
    predictor_name = args.predictor
    if args.mode == "stub":
        predictor_name = "stub"

    if args.mode == "real" and predictor_name == "mhcflurry" and not _have_mhcflurry():
        print("MHCflurry not installed")
        return 1

    predictor_fn = _build_predictor_fn(predictor_name)

    if args.mode == "both":
        stub_report = run_benchmark(
            dataset_path=dataset_path,
            cache_path=args.cache,
            output_path=args.output,
            predictor_fn=_build_predictor_fn("stub"),
            sleep_seconds=0.0,
            spearman_permutations=args.spearman_permutations,
            save_report=not args.no_save,
        )
        print_report(stub_report)
        print("Not biologically meaningful")
        print("")

    report = run_benchmark(
        dataset_path=dataset_path,
        cache_path=args.cache,
        output_path=args.output,
        predictor_fn=predictor_fn,
        sleep_seconds=args.sleep_seconds,
        spearman_permutations=args.spearman_permutations,
        save_report=not args.no_save,
    )
    print_report(report)

    if predictor_name == "stub" or report["predictor_used"] == "stub_fallback":
        print("Not biologically meaningful")

    if args.mode == "real" and predictor_name == "iedb" and report["predictor_used"] == "stub_fallback":
        print("IEDB API unavailable")
        return 1

    if not args.no_save:
        print("")
        print(f"Report saved to: {Path(args.output)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TESLA validation benchmark against the IEDB-backed real predictor.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--spearman-permutations", type=int, default=5000)
    parser.add_argument("--mode", choices=["stub", "real", "both"])
    parser.add_argument("--tesla-data")
    parser.add_argument("--predictor", choices=["auto", "iedb", "mhcflurry", "stub"], default="auto")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    if args.mode:
        raise SystemExit(_run_legacy_cli(args))

    report = run_benchmark(
        dataset_path=args.dataset,
        cache_path=args.cache,
        output_path=args.output,
        sleep_seconds=args.sleep_seconds,
        spearman_permutations=args.spearman_permutations,
    )
    print_report(report)
    print("")
    print(f"Report saved to: {Path(args.output)}")


if __name__ == "__main__":
    main()
