from __future__ import annotations

import builtins
import sqlite3
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from agent.learnings.store import LearningStore
from services.api.main import app


def _audit_statuses(db_path: str) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT action, status
            FROM audit_log
            WHERE action = 'entities_access'
            ORDER BY id ASC
            """
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def test_entities_access_logs_rejected_when_requester_missing(tmp_path, monkeypatch):
    db_path = str(tmp_path / "entities_audit_reject.db")
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", db_path)
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=db_path)
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="tester",
        metadata={"patient_id": "P-AUD-1", "sample_id": "S-AUD-1"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(f"/jobs/{job_id}/entities")

    assert resp.status_code == 403
    statuses = _audit_statuses(db_path)
    assert statuses
    assert statuses[-1] == ("entities_access", "rejected")


def test_entities_access_logs_rejected_for_non_phase2_job(tmp_path, monkeypatch):
    db_path = str(tmp_path / "entities_audit_allow.db")
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", db_path)
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=db_path)
    job_id = store.create_job(
        run_mode="dry_run",
        requested_by="tester",
        metadata={"patient_id": "P-AUD-2", "sample_id": "S-AUD-2"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(
        f"/jobs/{job_id}/entities",
        headers={"X-Requester-Id": "tester"},
    )

    assert resp.status_code == 400
    statuses = _audit_statuses(db_path)
    assert statuses
    assert statuses[-1] == ("entities_access", "rejected")


def test_entities_access_logs_allowed_in_postgres_mode(monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_DATABASE_URL", "postgresql://user:pass@localhost:5432/neoantigen")
    job_id = "job-entities-audit-allowed"

    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            job_id,
            "completed",
            "phase2_real",
            "tester",
            {"patient_id": "P-AUD-OK", "sample_id": "S-AUD-OK", "project_id": "PRJ-AUD"},
            "Worker finished",
            "2026-03-15T00:00:00Z",
            "2026-03-15T00:00:00Z",
        ),
        ("P-AUD-OK", "research_use_only", "PRJ-AUD"),
        ("S-AUD-OK", "P-AUD-OK", "tumor", "LIMS-AUD"),
        (1,),
        (1,),
    ]
    cursor.fetchall.side_effect = [
        [("run-aud-001", "s3://bucket/job-aud/tumor.fastq", "md5-aud", "illumina", "paired")],
        [("var-aud-001", "TP53", "missense_variant", 0.31, "clonal")],
        [("pep-aud-001", "ACGTACGTA", "HLA-A*02:01", "pred-aud-001", "model-v1", 0.9)],
    ]

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

    client = TestClient(app)
    resp = client.get(
        f"/jobs/{job_id}/entities",
        headers={
            "X-Requester-Id": "tester",
            "X-Project-Id": "PRJ-AUD",
        },
    )

    assert resp.status_code == 200
    executed_sql = [call.args[0].lower() for call in cursor.execute.call_args_list]
    assert any("insert into audit_log" in sql for sql in executed_sql)
