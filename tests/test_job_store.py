from __future__ import annotations

from services.api import job_store as job_store_module
from services.api.job_store import SqliteJobStore, get_job_store


def test_get_job_store_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("NEOANTIGEN_DATABASE_URL", raising=False)
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))

    store = get_job_store()
    assert isinstance(store, SqliteJobStore)

    job_id = store.create_job(run_mode="dry_run", requested_by="tester", metadata={"sample": "S1"})
    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"


def test_get_job_store_uses_postgres_backend_when_configured(monkeypatch):
    captured: dict[str, str] = {}

    class FakePostgresJobStore:
        def __init__(self, database_url: str) -> None:
            captured["database_url"] = database_url

    monkeypatch.setattr(job_store_module, "PostgresJobStore", FakePostgresJobStore)
    monkeypatch.setenv("NEOANTIGEN_DATABASE_URL", "postgresql://user:pass@localhost:5432/neo")

    store = get_job_store()
    assert isinstance(store, FakePostgresJobStore)
    assert captured["database_url"] == "postgresql://user:pass@localhost:5432/neo"
