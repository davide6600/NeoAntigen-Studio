import pytest

from services.worker import tcr_recognition

KNOWN = ("GILGFVFTL", "HLA-A*02:01")


def test_schema():
    r = tcr_recognition.predict_tcr_recognition(*KNOWN)
    assert hasattr(r, "score")
    assert hasattr(r, "method")
    assert 0.0 <= r.score <= 1.0
    assert r.method in {"prime2", "iedb_immunogenicity", "stub_tcr"}


def test_stub_deterministic():
    r1 = tcr_recognition.predict_tcr_recognition(*KNOWN, method="stub")
    r2 = tcr_recognition.predict_tcr_recognition(*KNOWN, method="stub")
    assert r1.score == r2.score


def test_stub_score_in_realistic_range():
    scores = [
        tcr_recognition.predict_tcr_recognition(
            f"PEPTIDE{i:02d}", "HLA-A*02:01", method="stub"
        ).score
        for i in range(20)
    ]
    assert all(0.25 <= s <= 0.85 for s in scores)
    assert len(set(round(s, 3) for s in scores)) > 10


@pytest.mark.network
def test_iedb_immunogenicity_api():
    r = tcr_recognition.predict_tcr_recognition(
        *KNOWN, method="iedb_immunogenicity"
    )
    if r.method == "stub_tcr":
        pytest.skip("IEDB API non raggiungibile")
    assert r.method == "iedb_immunogenicity"
    assert r.score is not None


def test_final_score_includes_tcr(monkeypatch):
    import services.worker.phase2_predictors as p2
    from services.worker import real_predictors, stability_predictor

    monkeypatch.setattr(
        real_predictors, "predict_binding",
        lambda p, a, prefer_offline=True, backend="auto": {
            "score": 0.8, "affinity_nm": 100.0,
            "percentile_rank": 1.0, "predictor": "stub_fallback",
        }
    )
    monkeypatch.setattr(
        stability_predictor, "predict_stability",
        lambda p, a: {
            "stability_score": 0.7, "thalf_hours": 6.0,
            "stability_backend": "stability_stub",
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
        tcr_recognition, "predict_tcr_recognition",
        lambda p, a, method="auto": tcr_recognition.TCRRecognitionResult(
            score=0.9,
            rank_percentile=None,
            method="stub_tcr",
            raw_output={},
        )
    )
    high_ranked, _, _ = p2.score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    monkeypatch.setattr(
        tcr_recognition, "predict_tcr_recognition",
        lambda p, a, method="auto": tcr_recognition.TCRRecognitionResult(
            score=0.1,
            rank_percentile=None,
            method="stub_tcr",
            raw_output={},
        )
    )
    low_ranked, _, _ = p2.score_phase2_candidates(
        sequence="ACGT" * 100,
        variants=variants,
        predictor_mode="ensemble_wrappers",
    )

    assert high_ranked[0]["final_score"] > low_ranked[0]["final_score"]
    assert "tcr_score" in high_ranked[0]
    assert "tcr_method" in high_ranked[0]
