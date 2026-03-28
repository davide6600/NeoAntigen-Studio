import pytest

from services.worker import stability_predictor

KNOWN_BINDER = ("GILGFVFTL", "HLA-A*02:01")


def test_schema_always_valid():
    result = stability_predictor.predict_stability(*KNOWN_BINDER)
    assert set(result.keys()) == {
        "stability_score", "thalf_hours", "stability_backend"
    }
    assert 0.0 <= result["stability_score"] <= 1.0
    assert result["stability_backend"] in \
           stability_predictor.VALID_STABILITY_BACKENDS


def test_stub_deterministic():
    r1 = stability_predictor._stability_stub(*KNOWN_BINDER)
    r2 = stability_predictor._stability_stub(*KNOWN_BINDER)
    assert r1 == r2
    assert r1["stability_backend"] == "stability_stub"


def test_stub_different_inputs_differ():
    r1 = stability_predictor._stability_stub("AAAAAAA", "HLA-A*02:01")
    r2 = stability_predictor._stability_stub("CCCCCCC", "HLA-A*02:01")
    assert r1["stability_score"] != r2["stability_score"]


def test_thalf_to_score_boundary():
    assert stability_predictor._thalf_to_score(0.5) == pytest.approx(0.0, abs=0.05)
    assert stability_predictor._thalf_to_score(8.0) == pytest.approx(1.0, abs=0.05)


@pytest.mark.network
def test_iedb_stability_api():
    result = stability_predictor.predict_stability_iedb(*KNOWN_BINDER)
    if result is None:
        pytest.skip("IEDB stability API non raggiungibile")
    assert result["stability_backend"] == "netmhcstabpan_iedb_api"
    assert result["stability_score"] >= 0.0


def test_final_score_incorporates_stability(monkeypatch):
    from services.worker import phase2_predictors, real_predictors

    monkeypatch.setattr(
        real_predictors, "predict_binding",
        lambda p, a, prefer_offline=True, backend="auto": {
            "score": 0.8, "affinity_nm": 100.0,
            "percentile_rank": 1.0, "predictor": "stub_fallback",
        }
    )

    variants = [{
        "variant_id": "var-001",
        "gene": "TP53",
        "position": 42,
        "ref": "A",
        "alt": "T",
        "effect": "missense_variant",
        "vaf": 0.31,
    }]

    monkeypatch.setattr(
        stability_predictor, "predict_stability",
        lambda p, a: {
            "stability_score": 0.9, "thalf_hours": 6.0,
            "stability_backend": "stability_stub",
        }
    )
    high_ranked, _, _ = phase2_predictors.score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    monkeypatch.setattr(
        stability_predictor, "predict_stability",
        lambda p, a: {
            "stability_score": 0.1, "thalf_hours": 0.2,
            "stability_backend": "stability_stub",
        }
    )
    low_ranked, _, _ = phase2_predictors.score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    assert high_ranked[0]["final_score"] > low_ranked[0]["final_score"]
    assert "stability_thalf" not in high_ranked[0]
    assert "thalf_hours" in high_ranked[0]
    assert "stability_score" in high_ranked[0]
    assert "stability_backend" in high_ranked[0]
