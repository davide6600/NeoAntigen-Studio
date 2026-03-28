from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from benchmark import run_tesla_benchmark as tesla


def test_benchmark_loads_csv():
    rows = tesla.load_tesla_dataset(tesla.DEFAULT_DATASET_PATH)
    assert len(rows) == 10
    assert tesla.REQUIRED_COLUMNS.issubset(rows[0].keys())


def test_benchmark_cache_read_write(tmp_path: Path):
    cache_path = tmp_path / "cache.json"
    cache = tesla.load_cache(cache_path)
    calls: list[tuple[str, str, bool]] = []

    def fake_predict_binding(peptide: str, allele: str, prefer_offline: bool = False) -> dict:
        calls.append((peptide, allele, prefer_offline))
        return {
            "score": 0.91,
            "affinity_nm": 42.0,
            "percentile_rank": 0.2,
            "predictor": "netmhcpan_iedb_api",
        }

    first_result, first_cache_hit = tesla.get_cached_or_predict(
        "GILGFVFTL",
        "HLA-A*02:01",
        cache,
        cache_path,
        predictor_fn=fake_predict_binding,
        sleep_seconds=0.0,
    )
    second_result, second_cache_hit = tesla.get_cached_or_predict(
        "GILGFVFTL",
        "HLA-A*02:01",
        cache,
        cache_path,
        predictor_fn=fake_predict_binding,
        sleep_seconds=0.0,
    )

    assert first_result == second_result
    assert first_cache_hit is False
    assert second_cache_hit is True
    assert calls == [("GILGFVFTL", "HLA-A*02:01", False)]

    saved_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved_cache["GILGFVFTL|HLA-A*02:01"]["affinity_nm"] == 42.0


def test_benchmark_metrics_calculation():
    perfect_metrics = tesla.calculate_metrics(
        [
            {"binding_score": 1.0, "affinity_nm": 25.0, "immunogenic": 1},
            {"binding_score": 0.9, "affinity_nm": 40.0, "immunogenic": 1},
            {"binding_score": 0.1, "affinity_nm": 5000.0, "immunogenic": 0},
            {"binding_score": 0.0, "affinity_nm": 8000.0, "immunogenic": 0},
        ],
        spearman_permutations=256,
    )
    random_metrics = tesla.calculate_metrics(
        [
            {"binding_score": 0.1, "affinity_nm": 25.0, "immunogenic": 1},
            {"binding_score": 0.8, "affinity_nm": 40.0, "immunogenic": 1},
            {"binding_score": 0.7, "affinity_nm": 5000.0, "immunogenic": 0},
            {"binding_score": 0.2, "affinity_nm": 8000.0, "immunogenic": 0},
        ],
        spearman_permutations=256,
    )

    assert perfect_metrics["auc_roc"] == 1.0
    assert perfect_metrics["auc_pr"] == 1.0
    assert abs(random_metrics["auc_roc"] - 0.5) < 1e-9


def test_benchmark_report_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output_path = tmp_path / "tesla_report.json"
    cache_path = tmp_path / "cache.json"

    def fake_predict_binding(peptide: str, allele: str, prefer_offline: bool = False) -> dict:
        positive = peptide in {"GILGFVFTL", "NLVPMVATV", "KLGGALQAK", "AVFDRKSDAK", "FLRGRAYGL"}
        return {
            "score": 0.95 if positive else 0.05,
            "affinity_nm": 35.0 if positive else 5000.0,
            "percentile_rank": 0.5 if positive else 60.0,
            "predictor": "netmhcpan_iedb_api",
        }

    monkeypatch.setattr(tesla.real_predictors, "predict_binding", fake_predict_binding)

    report = tesla.run_benchmark(
        dataset_path=tesla.DEFAULT_DATASET_PATH,
        cache_path=cache_path,
        output_path=output_path,
        sleep_seconds=0.0,
        spearman_permutations=256,
    )

    required_keys = {
        "date",
        "predictor_used",
        "n_peptides",
        "n_immunogenic",
        "n_non_immunogenic",
        "auc_roc",
        "auc_pr",
        "spearman_r",
        "spearman_p",
        "threshold_500nm",
        "per_peptide",
    }
    assert required_keys.issubset(report.keys())
    assert output_path.exists()

    saved_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert required_keys.issubset(saved_report.keys())
    assert len(saved_report["per_peptide"]) == 10


@pytest.mark.network
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skipped in CI: requires live IEDB API access",
)
def test_benchmark_real_api_gilgfvftl():
    result = tesla.real_predictors.predict_binding(
        "GILGFVFTL",
        "HLA-A*02:01",
        prefer_offline=False,
    )
    assert result["affinity_nm"] is not None
    assert result["affinity_nm"] < 100.0
