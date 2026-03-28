from __future__ import annotations

import builtins
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from agent.learnings.store import LearningStore
from services.api.main import app


def test_job_entities_requires_database_url_for_phase2_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "entities.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="tester",
        metadata={"patient_id": "P-001", "sample_id": "S-001"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(
        f"/jobs/{job_id}/entities",
        headers={"X-Requester-Id": "tester"},
    )

    assert resp.status_code == 400
    assert "NEOANTIGEN_DATABASE_URL" in resp.json()["detail"]


def test_job_entities_rejects_non_phase2_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "entities_non_phase2.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="dry_run",
        requested_by="tester",
        metadata={"patient_id": "P-002", "sample_id": "S-002"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(
        f"/jobs/{job_id}/entities",
        headers={"X-Requester-Id": "tester"},
    )

    assert resp.status_code == 400
    assert "phase2_real" in resp.json()["detail"]


def test_job_entities_returns_normalized_postgres_payload(tmp_path, monkeypatch):
    from services.api.config import get_settings
    get_settings.cache_clear()
    
    db_path = tmp_path / "entities.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_DATABASE_URL", "postgresql://user:pass@localhost:5432/neoantigen")
    
    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="tester",
        metadata={"patient_id": "P-001", "sample_id": "S-001"},
        message="Job accepted"
    )

    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            job_id,
            "completed",
            "phase2_real",
            "tester",
            {"patient_id": "P-001", "sample_id": "S-001", "project_id": "PRJ-01"},
            "Worker finished",
            "2026-03-15T00:00:00Z",
            "2026-03-15T00:00:00Z",
        ),
        ("P-001", "research_use_only", "PRJ-01"),
        ("S-001", "P-001", "tumor", "LIMS-01"),
        (1,),
        (1,),
    ]
    cursor.fetchall.side_effect = [
        [("run-001", "s3://bucket/job-1/tumor.fastq", "abcd", "illumina", "paired")],
        [("var-001", "TP53", "missense_variant", 0.32, "clonal")],
        [("pep-001", "ACGTACGTA", "HLA-A*02:01", "pred-001", "model-v1", 0.91)],
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
            "X-Project-Id": "PRJ-01",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["job_id"] == job_id
    assert payload["ruo"] is True
    assert payload["filters"]["limit"] == 50
    assert payload["filters"]["offset"] == 0
    assert payload["counts"]["variants_total"] == 1
    assert payload["counts"]["predictions_total"] == 1
    assert payload["patient"]["patient_id"] == "P-001"
    assert payload["sample"]["sample_id"] == "S-001"
    assert len(payload["sequence_runs"]) == 1
    assert len(payload["variants"]) == 1
    assert len(payload["predictions"]) == 1


def test_job_entities_applies_filters_and_pagination(tmp_path, monkeypatch):
    from services.api.config import get_settings
    get_settings.cache_clear()
    
    db_path = tmp_path / "entities_filters.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_DATABASE_URL", "postgresql://user:pass@localhost:5432/neoantigen")

    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="tester",
        metadata={"patient_id": "P-010", "sample_id": "S-010"},
        message="Job accepted",
    )

    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            job_id,
            "completed",
            "phase2_real",
            "tester",
            {"patient_id": "P-010", "sample_id": "S-010"},
            "Worker finished",
            "2026-03-15T00:00:00Z",
            "2026-03-15T00:00:00Z",
        ),
        ("P-010", "research_use_only", "PRJ-10"),
        ("S-010", "P-010", "tumor", "LIMS-10"),
        (3,),
        (2,),
    ]
    cursor.fetchall.side_effect = [
        [("run-010", "s3://bucket/job-10/tumor.fastq", "md5-10", "illumina", "paired")],
        [("var-010", "TP53", "missense_variant", 0.27, "subclonal")],
        [("pep-010", "ACGTACGTA", "HLA-A*02:01", "pred-010", "model-v1", 0.88)],
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
        f"/jobs/{job_id}/entities?limit=10&offset=5&gene=TP53&min_score=0.8",
        headers={"X-Requester-Id": "tester"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["filters"] == {"gene": "TP53", "min_score": 0.8, "limit": 10, "offset": 5}
    assert payload["counts"] == {"variants_total": 3, "predictions_total": 2}


def test_job_entities_requires_requester_header(tmp_path, monkeypatch):
    db_path = tmp_path / "entities_requires_requester.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="tester",
        metadata={"patient_id": "P-020", "sample_id": "S-020"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(f"/jobs/{job_id}/entities")

    assert resp.status_code == 403
    assert "X-Requester-Id" in resp.json()["detail"]


def test_job_entities_rejects_unauthorized_requester(tmp_path, monkeypatch):
    db_path = tmp_path / "entities_unauthorized.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)

    store = LearningStore(db_path=str(db_path))
    job_id = store.create_job(
        run_mode="phase2_real",
        requested_by="owner-user",
        metadata={"patient_id": "P-030", "sample_id": "S-030"},
        message="Job accepted",
    )

    client = TestClient(app)
    resp = client.get(
        f"/jobs/{job_id}/entities",
        headers={"X-Requester-Id": "different-user"},
    )

    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"]


def test_job_entities_rejects_project_scope_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_DATABASE_URL", "postgresql://user:pass@localhost:5432/neoantigen")
    job_id = "job-phase2-project-scope"

    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            job_id,
            "completed",
            "phase2_real",
            "tester",
            {"patient_id": "P-040", "sample_id": "S-040", "project_id": "PRJ-40"},
            "Worker finished",
            "2026-03-15T00:00:00Z",
            "2026-03-15T00:00:00Z",
        )
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
            "X-Project-Id": "PRJ-OTHER",
        },
    )

    assert resp.status_code == 403
    assert "project scope" in resp.json()["detail"]
