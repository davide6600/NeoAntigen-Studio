import pytest
from unittest.mock import patch, MagicMock

from services.worker import pvacseq_backend, real_predictors


def test_pvacseq_not_available_returns_none():
    with patch("services.worker.pvacseq_backend.is_pvacseq_available",
               return_value=False):
        result = pvacseq_backend.predict_binding_pvacseq(
            "GILGFVFTL", "HLA-A*02:01")
        assert result is None


def test_is_pvacseq_available_false_when_not_installed():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert pvacseq_backend.is_pvacseq_available() is False


def test_predict_binding_backend_stub():
    result = real_predictors.predict_binding(
        "GILGFVFTL", "HLA-A*02:01", backend="stub")
    assert result["predictor"] == "stub_fallback"
    assert 0.0 <= result["score"] <= 1.0


def test_predict_binding_backend_pvacseq_fallback_to_stub():
    with patch("services.worker.pvacseq_backend.is_pvacseq_available",
               return_value=False):
        result = real_predictors.predict_binding(
            "GILGFVFTL", "HLA-A*02:01", backend="pvacseq")
        assert result["predictor"] == "stub_fallback"


def test_predict_binding_backend_pvacseq_when_available():
    mock_result = {
        "score": 0.92, "affinity_nm": 45.0,
        "percentile_rank": 0.8, "predictor": "pvacseq",
        "pvacseq_version": "4.3.0"
    }
    with patch("services.worker.pvacseq_backend.is_pvacseq_available",
               return_value=True), \
         patch("services.worker.pvacseq_backend.run_pvacseq_single_peptide",
               return_value=mock_result):
        result = real_predictors.predict_binding(
            "GILGFVFTL", "HLA-A*02:01", backend="pvacseq")
        assert result["predictor"] == "pvacseq"
        assert result["affinity_nm"] == 45.0


def test_build_minimal_vcf_contains_peptide():
    vcf = pvacseq_backend._build_minimal_vcf("GILGFVFTL", "sample1")
    assert "GILGFVFTL" in vcf
    assert "#CHROM" in vcf
    assert "sample1" in vcf


@pytest.mark.slow
@pytest.mark.skipif(
    not pvacseq_backend.is_pvacseq_available(),
    reason="pvacseq not installed"
)
def test_pvacseq_real_known_binder():
    result = pvacseq_backend.predict_binding_pvacseq(
        "GILGFVFTL", "HLA-A*02:01")
    assert result is not None
    assert result["affinity_nm"] < 500.0
    assert result["predictor"] == "pvacseq"
