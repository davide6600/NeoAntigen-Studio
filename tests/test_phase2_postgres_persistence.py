from __future__ import annotations

import builtins
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.worker.phase2_postgres_persistence import persist_phase2_outputs


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_persist_phase2_outputs_no_database_url_returns_disabled(tmp_path):
    variants = _write_json(tmp_path / "variants.json", [])
    ranked = _write_json(tmp_path / "ranked.json", [])
    features = _write_json(tmp_path / "features.json", [])

    result = persist_phase2_outputs(
        database_url="",
        job_id="job-001",
        metadata={},
        pipeline_version="phase2-v0.2",
        image_digest="sha256:test",
        model_version="model-v1",
        parameters={},
        input_paths=[],
        variant_annotations_path=variants,
        ranked_peptides_path=ranked,
        feature_table_path=features,
    )

    assert result == {"enabled": False, "reason": "missing_database_url"}


def test_persist_phase2_outputs_executes_expected_writes(tmp_path, monkeypatch):
    variants = _write_json(
        tmp_path / "variants.json",
        [
            {
                "variant_id": "var-001",
                "position": 101,
                "ref": "A",
                "alt": "T",
                "gene": "TP53",
                "effect": "missense_variant",
                "vaf": 0.2,
            }
        ],
    )
    ranked = _write_json(
        tmp_path / "ranked.json",
        [
            {
                "peptide_id": "pep-001",
                "source_variant_id": "var-001",
                "peptide": "ACGTACGTA",
                "hla_allele": "HLA-A*02:01",
                "binding_score": 0.66,
                "expression_tpm": 12.5,
                "clonality": 0.42,
                "final_score": 0.71,
            }
        ],
    )
    features = _write_json(
        tmp_path / "features.json",
        [{"peptide_id": "pep-001", "binding_score": 0.66, "final_score": 0.71}],
    )

    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = None
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = None

    fake_psycopg = MagicMock()
    fake_psycopg.connect.return_value = connection

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result = persist_phase2_outputs(
        database_url="postgresql://user:pass@localhost:5432/neoantigen",
        job_id="job-001",
        metadata={"patient_id": "P-001", "sample_id": "S-001", "project_id": "PRJ-1"},
        pipeline_version="phase2-v0.2",
        image_digest="sha256:test",
        model_version="model-v1",
        parameters={"run_mode": "phase2_real"},
        input_paths=[str(tmp_path / "input.fastq")],
        variant_annotations_path=variants,
        ranked_peptides_path=ranked,
        feature_table_path=features,
    )

    assert result["enabled"] is True
    assert result["patient_id"] == "P-001"
    assert result["sample_id"] == "S-001"
    assert result["sequence_runs_persisted"] == 1
    assert result["variants_persisted"] == 1
    assert result["predictions_persisted"] == 1

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("insert into patient" in sql.lower() for sql in executed_sql)
    assert any("insert into sample" in sql.lower() for sql in executed_sql)
    assert any("insert into sequence_run" in sql.lower() for sql in executed_sql)
    assert any("insert into variant" in sql.lower() for sql in executed_sql)
    assert any("insert into peptide_candidate" in sql.lower() for sql in executed_sql)
    assert any("insert into prediction_record" in sql.lower() for sql in executed_sql)
    assert any("insert into provenance_record" in sql.lower() for sql in executed_sql)
