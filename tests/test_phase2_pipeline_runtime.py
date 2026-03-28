from __future__ import annotations

import json
from pathlib import Path

from services.worker.pipeline_runtime import run_phase2_pipeline


def test_run_phase2_pipeline_synthetic_writes_expected_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_PHASE2_ENGINE", "synthetic")

    result = run_phase2_pipeline(
        job_id="job-phase2-001",
        metadata={"sample_id": "S-001", "patient_id": "P-001"},
        input_paths=[],
        output_root=str(tmp_path),
    )

    assert result["engine"] == "synthetic"
    assert result["pipeline_version"] == "phase3-v0.1"
    assert result["summary"]["predictor_mode"] == "ensemble_seq2neo"
    assert result["summary"]["predictor_sources"] == ["pvactools", "netmhcpan", "mhcflurry", "seq2neo"]
    assert set(result["outputs"].keys()) == {
        "preprocessing_qc_json",
        "variant_annotations_json",
        "ranked_peptides_json",
        "feature_table_json",
    }

    for output_path in result["outputs"].values():
        assert Path(output_path).exists()


def test_run_phase2_pipeline_synthetic_is_deterministic_for_same_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_PHASE2_ENGINE", "synthetic")
    metadata = {"sample_id": "S-DET-001", "patient_id": "P-DET-001"}

    first = run_phase2_pipeline(
        job_id="job-phase2-det",
        metadata=metadata,
        input_paths=[],
        output_root=str(tmp_path),
    )
    second = run_phase2_pipeline(
        job_id="job-phase2-det",
        metadata=metadata,
        input_paths=[],
        output_root=str(tmp_path),
    )

    ranked_first = json.loads(Path(first["outputs"]["ranked_peptides_json"]).read_text(encoding="utf-8"))
    ranked_second = json.loads(Path(second["outputs"]["ranked_peptides_json"]).read_text(encoding="utf-8"))
    feature_table = json.loads(Path(first["outputs"]["feature_table_json"]).read_text(encoding="utf-8"))

    assert ranked_first == ranked_second
    assert first["summary"] == second["summary"]
    assert ranked_first[0]["predictor_mode"] == "ensemble_seq2neo"
    assert "pvactools_score" in feature_table[0]
    assert "netmhcpan_score" in feature_table[0]
    assert "mhcflurry_score" in feature_table[0]
