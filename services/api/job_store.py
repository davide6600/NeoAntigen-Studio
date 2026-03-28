from __future__ import annotations

import json
import os
import uuid

from agent.learnings.store import LearningStore


class JobStore:
    def create_job(self, run_mode: str, requested_by: str, metadata: dict, message: str | None = None) -> str:
        raise NotImplementedError

    def update_job_status(self, job_id: str, status: str, message: str | None = None) -> None:
        raise NotImplementedError

    def get_job(self, job_id: str) -> dict | None:
        raise NotImplementedError

    def append_job_audit_event(
        self, job_id: str, step: str, status: str, duration_ms: int, details: dict
    ) -> None:
        raise NotImplementedError

    def list_job_audit_events(self, job_id: str) -> list[dict]:
        raise NotImplementedError

    def get_job_logs(self, job_id: str) -> list[dict]:
        raise NotImplementedError

    def add_job_artifact(
        self,
        job_id: str,
        artifact_type: str,
        path: str,
        size_bytes: int,
        md5: str | None = None,
        content_type: str | None = None,
    ) -> None:
        raise NotImplementedError

    def list_job_artifacts(self, job_id: str) -> list[dict]:
        raise NotImplementedError

    def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        raise NotImplementedError

    def add_job_step(
        self,
        job_id: str,
        step_id: str,
        name: str,
        status: str,
        input_data: dict | None = None,
    ) -> None:
        raise NotImplementedError

    def update_job_step(
        self,
        job_id: str,
        step_id: str,
        status: str,
        output_data: dict | None = None,
        is_manually_edited: bool = False,
    ) -> None:
        raise NotImplementedError

    def get_job_steps(self, job_id: str) -> list[dict]:
        raise NotImplementedError


class SqliteJobStore(JobStore):
    def __init__(self, db_path: str) -> None:
        self._store = LearningStore(db_path=db_path)
        self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        with self._store._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    step TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def append_job_audit_event(
        self, job_id: str, step: str, status: str, duration_ms: int, details: dict
    ) -> None:
        with self._store._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_audit_events (job_id, step, status, duration_ms, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, step, status, duration_ms, json.dumps(details)),
            )

    def list_job_audit_events(self, job_id: str) -> list[dict]:
        with self._store._connect() as conn:
            rows = conn.execute(
                """
                SELECT step, status, duration_ms, details_json, created_at
                FROM job_audit_events
                WHERE job_id = ?
                ORDER BY created_at ASC
                """,
                (job_id,),
            ).fetchall()

        return [
            {
                "step": row[0],
                "status": row[1],
                "duration_ms": row[2],
                "details": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]

    def create_job(self, run_mode: str, requested_by: str, metadata: dict, message: str | None = None) -> str:
        return self._store.create_job(run_mode=run_mode, requested_by=requested_by, metadata=metadata, message=message)

    def update_job_status(self, job_id: str, status: str, message: str | None = None) -> None:
        self._store.update_job_status(job_id=job_id, status=status, message=message)

    def get_job(self, job_id: str) -> dict | None:
        return self._store.get_job(job_id)

    def get_job_logs(self, job_id: str) -> list[dict]:
        return self._store.get_job_logs(job_id)

    def add_job_artifact(
        self,
        job_id: str,
        artifact_type: str,
        path: str,
        size_bytes: int,
        md5: str | None = None,
        content_type: str | None = None,
    ) -> None:
        self._store.add_job_artifact(
            job_id=job_id,
            artifact_type=artifact_type,
            path=path,
            size_bytes=size_bytes,
            md5=md5,
            content_type=content_type,
        )

    def list_job_artifacts(self, job_id: str) -> list[dict]:
        return self._store.list_job_artifacts(job_id)

    def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return self._store.list_jobs(limit=limit, offset=offset)

    def add_job_step(
        self,
        job_id: str,
        step_id: str,
        name: str,
        status: str,
        input_data: dict | None = None,
    ) -> None:
        self._store.add_job_step(job_id=job_id, step_id=step_id, name=name, status=status, input_data=input_data)

    def update_job_step(
        self,
        job_id: str,
        step_id: str,
        status: str,
        output_data: dict | None = None,
        is_manually_edited: bool = False,
    ) -> None:
        self._store.update_job_step(
            job_id=job_id,
            step_id=step_id,
            status=status,
            output_data=output_data,
            is_manually_edited=is_manually_edited,
        )

    def get_job_steps(self, job_id: str) -> list[dict]:
        return self._store.get_job_steps(job_id)


class PostgresJobStore(JobStore):
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("postgresql://") and not database_url.startswith("postgres://"):
            raise ValueError("Only PostgreSQL URLs are supported for PostgresJobStore")
        self._database_url = database_url
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL job persistence. Install with: pip install psycopg[binary]"
            ) from exc
        self._psycopg = psycopg
        self._init_schema()

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        run_mode TEXT NOT NULL,
                        requested_by TEXT NOT NULL,
                        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        message TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_artifacts (
                        id BIGSERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                        artifact_type TEXT NOT NULL,
                        path TEXT NOT NULL,
                        md5 TEXT,
                        size_bytes BIGINT NOT NULL,
                        content_type TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_steps (
                        id BIGSERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                        step_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        input_data_json JSONB,
                        output_data_json JSONB,
                        is_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE(job_id, step_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        action TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_audit_events (
                        id BIGSERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                        step TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration_ms BIGINT NOT NULL,
                        details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            conn.commit()

    def append_job_audit_event(
        self, job_id: str, step: str, status: str, duration_ms: int, details: dict
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_audit_events (job_id, step, status, duration_ms, details_json)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (job_id, step, status, duration_ms, json.dumps(details)),
                )
            conn.commit()

    def list_job_audit_events(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT step, status, duration_ms, details_json, created_at
                    FROM job_audit_events
                    WHERE job_id = %s
                    ORDER BY created_at ASC
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()

        return [
            {
                "step": row[0],
                "status": row[1],
                "duration_ms": row[2],
                "details": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                "timestamp": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }
            for row in rows
        ]

    def _append_audit_event(self, action: str, status: str, details: dict) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log (action, status, details_json)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (action, status, json.dumps(details)),
                )
            conn.commit()

    def create_job(self, run_mode: str, requested_by: str, metadata: dict, message: str | None = None) -> str:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO jobs (job_id, status, run_mode, requested_by, metadata_json, message)
                    VALUES (%s, 'queued', %s, %s, %s::jsonb, %s)
                    """,
                    (job_id, run_mode, requested_by, json.dumps(metadata), message),
                )
            conn.commit()

        self._append_audit_event(
            action="job_status_transition",
            status="queued",
            details={"job_id": job_id, "run_mode": run_mode, "requested_by": requested_by},
        )
        return job_id

    def update_job_status(self, job_id: str, status: str, message: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = %s, message = COALESCE(%s, message), updated_at = now()
                    WHERE job_id = %s
                    """,
                    (status, message, job_id),
                )
            conn.commit()

        self._append_audit_event(
            action="job_status_transition",
            status=status,
            details={"job_id": job_id, "message": message},
        )

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id, status, run_mode, requested_by, metadata_json, message, created_at, updated_at
                    FROM jobs
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None

        return {
            "job_id": row[0],
            "status": row[1],
            "run_mode": row[2],
            "requested_by": row[3],
            "metadata": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
            "message": row[5],
            "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
            "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
        }

    def get_job_logs(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, action, status, details_json, created_at
                    FROM audit_log
                    WHERE details_json->>'job_id' = %s
                    ORDER BY id ASC
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "action": row[1],
                "status": row[2],
                "details": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }
            for row in rows
        ]

    def add_job_artifact(
        self,
        job_id: str,
        artifact_type: str,
        path: str,
        size_bytes: int,
        md5: str | None = None,
        content_type: str | None = None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_artifacts (job_id, artifact_type, path, md5, size_bytes, content_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (job_id, artifact_type, path, md5, size_bytes, content_type),
                )
            conn.commit()

    def list_job_artifacts(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT artifact_type, path, md5, size_bytes, content_type, created_at
                    FROM job_artifacts
                    WHERE job_id = %s
                    ORDER BY id ASC
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()

        return [
            {
                "artifact_type": row[0],
                "path": row[1],
                "md5": row[2],
                "size_bytes": row[3],
                "content_type": row[4],
                "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }
            for row in rows
        ]

    def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id, status, run_mode, requested_by, metadata_json, message, created_at, updated_at
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()

        return [
            {
                "job_id": row[0],
                "status": row[1],
                "run_mode": row[2],
                "requested_by": row[3],
                "metadata": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                "message": row[5],
                "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
            }
            for row in rows
        ]

    def add_job_step(
        self,
        job_id: str,
        step_id: str,
        name: str,
        status: str,
        input_data: dict | None = None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_steps (job_id, step_id, name, status, input_data_json)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (job_id, step_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        input_data_json = COALESCE(EXCLUDED.input_data_json, job_steps.input_data_json),
                        updated_at = now()
                    """,
                    (job_id, step_id, name, status, json.dumps(input_data) if input_data else None),
                )
            conn.commit()

    def update_job_step(
        self,
        job_id: str,
        step_id: str,
        status: str,
        output_data: dict | None = None,
        is_manually_edited: bool = False,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_steps
                    SET status = %s, 
                        output_data_json = COALESCE(%s::jsonb, output_data_json), 
                        is_manually_edited = %s, 
                        updated_at = now()
                    WHERE job_id = %s AND step_id = %s
                    """,
                    (status, json.dumps(output_data) if output_data else None, is_manually_edited, job_id, step_id),
                )
            conn.commit()

    def get_job_steps(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT step_id, name, status, input_data_json, output_data_json, is_manually_edited, created_at, updated_at
                    FROM job_steps
                    WHERE job_id = %s
                    ORDER BY created_at ASC
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()

        return [
            {
                "step_id": row[0],
                "name": row[1],
                "status": row[2],
                "input_data": row[3] if isinstance(row[3], dict) else (json.loads(row[3]) if row[3] else None),
                "output_data": row[4] if isinstance(row[4], dict) else (json.loads(row[4]) if row[4] else None),
                "is_manually_edited": row[5],
                "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
            }
            for row in rows
        ]


def get_job_store(db_path_override: str | None = None) -> JobStore:
    database_url = os.getenv("NEOANTIGEN_DATABASE_URL", "").strip()
    if database_url:
        return PostgresJobStore(database_url=database_url)

    db_path = db_path_override or os.getenv("NEOANTIGEN_LEARNINGS_DB", "agent/learnings/learnings.db")
    return SqliteJobStore(db_path=db_path)