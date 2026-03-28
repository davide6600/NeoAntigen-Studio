#!/usr/bin/env python3
"""
TESLA benchmark: call IEDB tools_api (netmhcpan_ba) for validated peptides
and compute simple AUC-ROC + precision/recall. Saves cache and report.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
import sys

# ensure project root is on sys.path so we can import services.worker
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.worker import real_predictors

IEDB_URL = "https://tools.iedb.org/tools_api/mhci/"


def query_iedb(peptide: str, allele: str) -> dict | None:
    """Delegate to services.worker.real_predictors.predict_binding_iedb_api()."""
    try:
        result = real_predictors.predict_binding_iedb_api(peptide, allele)
        return result
    except Exception as e:
        print(f"  IEDB wrapper error for {peptide}/{allele}: {e}")
        return None


def auc_roc(scores, labels):
    pairs = sorted(zip(scores, labels), reverse=True)
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    wins = 0.0
    for s_pos in [s for l, s in zip(labels, scores) if l == 1]:
        for s_neg in [s for l, s in zip(labels, scores) if l == 0]:
            if s_pos > s_neg:
                wins += 1.0
            elif s_pos == s_neg:
                wins += 0.5
    return wins / (pos * neg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default=str(Path(__file__).with_name("cache_real.json")))
    parser.add_argument("--dataset", default=str(Path(__file__).with_name("tesla_validated.csv")))
    parser.add_argument("--output", default=str(Path(__file__).parent / "results" / "tesla_report.json"))
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore existing cache, force live API calls")
    args = parser.parse_args()

    cache_path = Path(args.cache)
    if args.no_cache:
        cache = {}
    else:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    dataset = Path(args.dataset)
    rows = list(csv.DictReader(open(dataset, "r", encoding="utf-8", newline="")))

    results = []
    for row in rows:
        peptide = row["peptide"].strip()
        allele = row["hla_allele"].strip()
        immunog = int(row["immunogenic"])
        key = f"{peptide}|{allele}"

        if (not args.no_cache) and key in cache:
            pred = cache[key]
            print(f"  [CACHE] {peptide} / {allele} → IC50={pred.get('affinity_nm')} nM")
        else:
            print(f"  [API]   {peptide} / {allele} ...", end=" ", flush=True)
            pred = query_iedb(peptide, allele)
            if pred:
                cache[key] = pred
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                print(f"IC50={pred['affinity_nm']} nM, score={pred['score']}")
                time.sleep(float(args.sleep_seconds))
            else:
                pred = {"score": 0.5, "affinity_nm": None, "percentile_rank": None, "predictor": "api_failed"}
                print("FAILED")

        results.append({
            "patient_id": row.get("patient_id", ""),
            "peptide": peptide,
            "allele": allele,
            "immunogenic": immunog,
            "score": pred["score"],
            "affinity_nm": pred.get("affinity_nm"),
            "percentile_rank": pred.get("percentile_rank"),
            "predictor": pred.get("predictor"),
        })

    scores = [r["score"] for r in results]
    labels = [r["immunogenic"] for r in results]
    roc = auc_roc(scores, labels)

    # Precision/Recall at score > 0.5
    pred_pos = [1 if s > 0.5 else 0 for s in scores]
    tp = sum(1 for p, l in zip(pred_pos, labels) if p == 1 and l == 1)
    fp = sum(1 for p, l in zip(pred_pos, labels) if p == 1 and l == 0)
    fn = sum(1 for p, l in zip(pred_pos, labels) if p == 0 and l == 1)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    report = {
        "date": datetime.now().isoformat(),
        "predictor_used": "netmhcpan_iedb_api",
        "n_peptides": len(results),
        "n_immunogenic": sum(labels),
        "n_non_immunogenic": len(labels) - sum(labels),
        "auc_roc": round(roc, 4) if roc else None,
        "threshold_500nm": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "per_peptide": results,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print("RISULTATI BENCHMARK")
    print(f"{'='*50}")
    print(f"  Peptidi totali:     {report['n_peptides']}")
    print(f"  Immunogenici:       {report['n_immunogenic']}")
    print(f"  Non-immunogenici:   {report['n_non_immunogenic']}")
    print(f"  AUC-ROC:            {report['auc_roc']}")
    print(f"\n  Report: {out}")


if __name__ == "__main__":
    main()
