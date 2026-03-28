import pytest
from services.worker import real_predictors

KNOWN_BINDER = ("GILGFVFTL", "HLA-A*02:01")


def test_schema_always_valid():
    result = real_predictors.predict_binding(*KNOWN_BINDER)
    assert set(result.keys()) == {"score", "affinity_nm", "percentile_rank", "predictor"}
    assert 0.0 <= result["score"] <= 1.0
    assert result["predictor"] in real_predictors.VALID_PREDICTORS


def test_stub_deterministic():
    assert real_predictors._stub_fallback(*KNOWN_BINDER) == \
           real_predictors._stub_fallback(*KNOWN_BINDER)


def test_stub_different_inputs_differ():
    assert real_predictors._stub_fallback("AAAAAAA", "HLA-A*02:01")["score"] != \
           real_predictors._stub_fallback("CCCCCCC", "HLA-A*02:01")["score"]
