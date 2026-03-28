from __future__ import annotations

import pytest

from services.worker import real_predictors
from services.worker.phase2_predictors import score_phase2_candidates


def _mock_binding_result() -> dict:
    return {
        "score": 0.75,
        "affinity_nm": 150.0,
        "percentile_rank": 2.5,
        "predictor": "stub_fallback",
    }


def test_phase2_predictor_wrappers_return_ensemble_fields(monkeypatch) -> None:
    monkeypatch.setattr(real_predictors, "predict_binding", lambda *args, **kwargs: _mock_binding_result())
    monkeypatch.setattr(real_predictors, "get_available_predictor", lambda: "stub_fallback")
    variants = [
        {
            "variant_id": "var-001",
            "gene": "TP53",
            "position": 42,
            "ref": "A",
            "alt": "T",
            "effect": "missense_variant",
            "vaf": 0.31,
        }
    ]

    ranked, feature_table, summary = score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    assert summary["predictor_mode"] == "ensemble_wrappers"
    assert len(summary["predictor_sources"]) == 1
    assert summary["predictor_sources"][0] in real_predictors.VALID_PREDICTORS
    assert ranked[0]["predictor_mode"] == "ensemble_wrappers"
    assert ranked[0]["predictor_used"] == "stub_fallback"
    assert ranked[0]["affinity_nm"] == 150.0
    assert ranked[0]["percentile_rank"] == 2.5
    assert feature_table[0]["predictor_mode"] == "ensemble_wrappers"
    assert feature_table[0]["binding_score"] == 0.75
    assert feature_table[0]["affinity_nm"] == 150.0
    assert feature_table[0]["predictor_used"] == "stub_fallback"
    assert "pvactools_stub_score" not in feature_table[0]
    assert "netmhcpan_stub_score" not in feature_table[0]
    assert "mhcflurry_stub_score" not in feature_table[0]


# Requires live IEDB + stability API access.
# Excluded in CI and local runs via -m "not network and not slow".
@pytest.mark.network
@pytest.mark.slow
def test_phase2_predictor_wrappers_are_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(real_predictors, "predict_binding", lambda *args, **kwargs: _mock_binding_result())
    monkeypatch.setattr(real_predictors, "get_available_predictor", lambda: "stub_fallback")
    variants = [
        {
            "variant_id": "var-001",
            "gene": "KRAS",
            "position": 55,
            "ref": "G",
            "alt": "T",
            "effect": "missense_variant",
            "vaf": 0.22,
        }
    ]

    first = score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )
    second = score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    assert first == second


def test_expression_file_adds_tpm_column(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(real_predictors, "predict_binding", lambda *args, **kwargs: _mock_binding_result())
    monkeypatch.setattr(real_predictors, "get_available_predictor", lambda: "stub_fallback")
    variants = [
        {
            "variant_id": "var-001",
            "gene": "TP53",
            "position": 42,
            "ref": "A",
            "alt": "T",
            "effect": "missense_variant",
            "vaf": 0.31,
        }
    ]

    # Create a small TSV expression file with TPMs (TP53 passes threshold)
    expr_file = tmp_path / "expr.tsv"
    expr_file.write_text("gene_id\ttpm\nTP53\t12.3\nKRAS\t0.2\n", encoding="utf-8")

    ranked, feature_table, summary = score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
        expression_file=str(expr_file),
    )

    assert len(ranked) > 0
    assert "tpm" in ranked[0], "TPM column should be present when expression_file is provided"


def test_no_expression_file_no_tpm_column(monkeypatch) -> None:
    monkeypatch.setattr(real_predictors, "predict_binding", lambda *args, **kwargs: _mock_binding_result())
    monkeypatch.setattr(real_predictors, "get_available_predictor", lambda: "stub_fallback")
    variants = [
        {
            "variant_id": "var-001",
            "gene": "KRAS",
            "position": 55,
            "ref": "G",
            "alt": "T",
            "effect": "missense_variant",
            "vaf": 0.22,
        }
    ]

    ranked, feature_table, summary = score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    assert len(ranked) > 0
    assert "tpm" not in ranked[0], "TPM column should not be present when no expression_file is provided"
