from __future__ import annotations

import json
import subprocess
import sys

import pytest

from benchmark.tesla_benchmark import (
    BenchmarkResult,
    TESLA_VALIDATED_PEPTIDES,
    _compute_auprc,
    compare_with_literature,
    run_benchmark,
    save_benchmark_report,
)


def test_benchmark_returns_valid_result():
    result = run_benchmark(backend="stub")
    assert isinstance(result, BenchmarkResult)
    assert result.n_tested == len(TESLA_VALIDATED_PEPTIDES)
    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert 0.0 <= result.f1_score <= 1.0
    assert 0.0 <= result.auprc <= 1.0


def test_benchmark_tp_fp_tn_fn_sum_to_total():
    result = run_benchmark(backend="stub")
    total = (
        result.n_true_positives
        + result.n_false_positives
        + result.n_true_negatives
        + result.n_false_negatives
    )
    assert total == result.n_tested


def test_score_separation_meaningful():
    result = run_benchmark(backend="stub")
    assert not (result.score_separation != result.score_separation)
    assert abs(result.score_separation) < 2.0


def test_auprc_computation():
    perfect = [
        {"validated": True, "binding_score": 0.9},
        {"validated": True, "binding_score": 0.8},
        {"validated": False, "binding_score": 0.2},
        {"validated": False, "binding_score": 0.1},
    ]
    auprc = _compute_auprc(perfect)
    assert auprc > 0.8


def test_compare_with_literature_has_all_pipelines():
    literature = compare_with_literature()
    assert "pVACseq" in literature
    assert "NetMHCpan" in literature
    for _, values in literature.items():
        assert "precision" in values and "recall" in values and "f1" in values


def test_benchmark_per_peptide_has_correct_fields():
    result = run_benchmark(backend="stub")
    required = {"peptide", "hla", "validated", "binding_score", "predicted_positive", "correct", "predictor"}
    for entry in result.per_peptide:
        assert required.issubset(entry.keys())


def test_save_benchmark_report(tmp_path):
    result = run_benchmark(backend="stub")
    json_path = save_benchmark_report(result, tmp_path)
    assert json_path.exists()
    csv_path = tmp_path / "tesla_benchmark_per_peptide.csv"
    assert csv_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "summary" in data and "per_peptide" in data


def test_benchmark_warns_on_stub():
    completed = subprocess.run(
        [sys.executable, "-m", "benchmark.run_tesla_benchmark", "--mode", "stub", "--no-save"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    combined = f"{completed.stdout}\n{completed.stderr}"
    assert "stub_fallback" in combined
    assert "Not biologically meaningful" in combined


def test_real_mode_accepts_iedb_predictor_with_csv(tmp_path):
    tesla_csv = tmp_path / "tesla.csv"
    tesla_csv.write_text(
        "patient_id,peptide,hla_allele,immunogenic\nTESLA_P1,GILGFVFTL,HLA-A*02:01,1\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmark.run_tesla_benchmark",
            "--mode",
            "real",
            "--predictor",
            "iedb",
            "--tesla-data",
            str(tesla_csv),
            "--no-save",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        assert "Predictor used:" in completed.stdout
    else:
        combined = f"{completed.stdout}\n{completed.stderr}"
        assert "IEDB API unavailable" in combined


def _mhcflurry_installed() -> bool:
    try:
        from mhcflurry import Class1PresentationPredictor

        Class1PresentationPredictor.load()
        return True
    except Exception:
        return False


@pytest.mark.skipif(_mhcflurry_installed(), reason="mhcflurry installed")
def test_real_mode_skipped_without_mhcflurry(tmp_path):
    tesla_csv = tmp_path / "tesla.csv"
    tesla_csv.write_text(
        "patient_id,peptide,hla_allele,immunogenic\nTESLA_P1,GILGFVFTL,HLA-A*02:01,1\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmark.run_tesla_benchmark",
            "--mode",
            "real",
            "--predictor",
            "mhcflurry",
            "--tesla-data",
            str(tesla_csv),
            "--no-save",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    combined = f"{completed.stdout}\n{completed.stderr}"
    assert "MHCflurry not installed" in combined
