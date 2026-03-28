from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class LearningRecord:
    training_data_id: str
    model_version: str
    metrics: dict[str, float]
    commit_hash: str
    timestamp: str
    notes: str
    decision_rules: list[str]
    top_features: list[str]
    misclassifications: list[str]
    stage: str = "staging"


class LearningStore:
    def __init__(self, db_path: str = "agent/learnings/learnings.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    training_data_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decision_rules_json TEXT NOT NULL,
                    top_features_json TEXT NOT NULL,
                    misclassifications_json TEXT NOT NULL,
                    stage TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS label_ingestions (
                    batch_id TEXT PRIMARY KEY,
                    total_count INTEGER NOT NULL,
                    accepted_count INTEGER NOT NULL,
                    flagged_count INTEGER NOT NULL,
                    high_uncertainty_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    peptide_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    proposal_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    resolved_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consent_records (
                    patient_id TEXT PRIMARY KEY,
                    consent_status TEXT NOT NULL,
                    allowed_uses_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    soft_deleted INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deletion_requests (
                    request_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    requester_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    executed_at TEXT,
                    executed_by TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    run_mode TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    md5 TEXT,
                    size_bytes INTEGER NOT NULL,
                    content_type TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_data_json TEXT,
                    output_data_json TEXT,
                    is_manually_edited INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(job_id, step_id)
                )
                """
            )

    def record_learning(self, record: LearningRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_records (
                    training_data_id, model_version, metrics_json, commit_hash, timestamp,
                    notes, decision_rules_json, top_features_json, misclassifications_json, stage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.training_data_id,
                    record.model_version,
                    json.dumps(record.metrics),
                    record.commit_hash,
                    record.timestamp,
                    record.notes,
                    json.dumps(record.decision_rules),
                    json.dumps(record.top_features),
                    json.dumps(record.misclassifications),
                    record.stage,
                ),
            )

    def get_last_learnings(self, limit: int = 5) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT training_data_id, model_version, metrics_json, commit_hash, timestamp, stage
                FROM learning_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "training_data_id": row[0],
                    "model_version": row[1],
                    "metrics": json.loads(row[2]),
                    "commit_hash": row[3],
                    "timestamp": row[4],
                    "stage": row[5],
                }
            )
        return result

    def model_summary(self) -> dict:
        return {
            "versions": self.get_last_learnings(limit=10),
            "training_date": self.get_last_learnings(limit=1)[0]["timestamp"] if self.get_last_learnings(limit=1) else None,
        }

    def log_label_ingestion(self, total_count: int, accepted_count: int, flagged_count: int, high_uncertainty_count: int) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(batch_id, 7) AS INTEGER)), 0) FROM label_ingestions").fetchone()
            next_id = int(row[0]) + 1
            batch_id = f"batch-{next_id:05d}"
            conn.execute(
                """
                INSERT INTO label_ingestions (batch_id, total_count, accepted_count, flagged_count, high_uncertainty_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (batch_id, total_count, accepted_count, flagged_count, high_uncertainty_count),
            )
        return batch_id

    def log_acquisition_batch(self, batch_id: str, peptide_ids: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO acquisition_batches (batch_id, peptide_ids_json) VALUES (?, ?)",
                (batch_id, json.dumps(peptide_ids)),
            )

    def append_audit_event(self, action: str, status: str, details: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (action, status, details_json) VALUES (?, ?, ?)",
                (action, status, json.dumps(details)),
            )

    def add_pending_approval(self, proposal_id: str, action: str, details: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_approvals (proposal_id, action, details_json, status)
                VALUES (?, ?, ?, 'pending')
                ON CONFLICT(proposal_id) DO UPDATE SET action=excluded.action, details_json=excluded.details_json, status='pending', resolved_at=NULL
                """,
                (proposal_id, action, json.dumps(details)),
            )

    def list_pending_approvals(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT proposal_id, action, details_json, created_at
                FROM pending_approvals
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "proposal_id": r[0],
                "action": r[1],
                "details": json.loads(r[2]),
                "created_at": r[3],
            }
            for r in rows
        ]

    def get_pending_approvals(self, limit: int = 10) -> list[dict]:
        return self.list_pending_approvals(limit=limit)

    def resolve_approval(self, proposal_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE pending_approvals SET status='approved', resolved_at=datetime('now') WHERE proposal_id=?",
                (proposal_id,),
            )

    def suggest_retrain(self, label_delta_threshold: int = 25, metric_drift_threshold: float = 0.05) -> dict:
        with self._connect() as conn:
            label_total_row = conn.execute(
                "SELECT COALESCE(SUM(total_count), 0) FROM label_ingestions"
            ).fetchone()
            latest_two = conn.execute(
                "SELECT metrics_json, model_version, timestamp FROM learning_records ORDER BY id DESC LIMIT 2"
            ).fetchall()

        label_total = int(label_total_row[0])
        reasons: list[str] = []

        if label_total >= label_delta_threshold:
            reasons.append(f"label_count_delta_exceeded:{label_total}")

        drift = 0.0
        if len(latest_two) >= 2:
            latest_metrics = json.loads(latest_two[0][0])
            previous_metrics = json.loads(latest_two[1][0])
            latest_auprc = float(latest_metrics.get("auprc", 0.0))
            previous_auprc = float(previous_metrics.get("auprc", 0.0))
            drift = previous_auprc - latest_auprc
            if drift >= metric_drift_threshold:
                reasons.append(f"metric_drift_detected:{round(drift, 6)}")

        recommend = len(reasons) > 0
        return {
            "recommend_retrain": recommend,
            "target_stage": "staging",
            "auto_promote_to_production": False,
            "reasons": reasons,
            "label_total": label_total,
            "metric_drift": drift,
        }

    # ------------------------------------------------------------------
    # Consent and retention / deletion
    # ------------------------------------------------------------------

    def record_consent(
        self,
        patient_id: str,
        consent_status: str,
        allowed_uses: list[str],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO consent_records
                    (patient_id, consent_status, allowed_uses_json, recorded_at, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    consent_status = excluded.consent_status,
                    allowed_uses_json = excluded.allowed_uses_json,
                    soft_deleted = 0,
                    last_updated = excluded.last_updated
                """,
                (patient_id, consent_status, json.dumps(allowed_uses), now, now),
            )

    def get_consent_record(self, patient_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT patient_id, consent_status, allowed_uses_json, recorded_at
                FROM consent_records
                WHERE patient_id = ? AND soft_deleted = 0
                """,
                (patient_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "patient_id": row[0],
            "consent_status": row[1],
            "allowed_uses": json.loads(row[2]),
            "recorded_at": row[3],
        }

    def soft_delete_consent(self, patient_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE consent_records SET soft_deleted = 1, last_updated = ? WHERE patient_id = ?",
                (now, patient_id),
            )

    def create_deletion_request(
        self,
        patient_id: str,
        reason: str,
        requester_id: str,
    ) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(request_id, 5) AS INTEGER)), 0) FROM deletion_requests"
            ).fetchone()
            next_id = int(row[0]) + 1
            request_id = f"del-{next_id:05d}"
            conn.execute(
                """
                INSERT INTO deletion_requests (request_id, patient_id, reason, requester_id, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (request_id, patient_id, reason, requester_id),
            )
        return request_id

    def get_deletion_request(self, request_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT request_id, patient_id, reason, requester_id, status
                FROM deletion_requests
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "request_id": row[0],
            "patient_id": row[1],
            "reason": row[2],
            "requester_id": row[3],
            "status": row[4],
        }

    def mark_deletion_request_executed(self, request_id: str, executed_by: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE deletion_requests
                SET status = 'executed', executed_at = ?, executed_by = ?
                WHERE request_id = ?
                """,
                (now, executed_by, request_id),
            )

    # ------------------------------------------------------------------
    # Job lifecycle and artifacts
    # ------------------------------------------------------------------

    def create_job(
        self,
        run_mode: str,
        requested_by: str,
        metadata: dict,
        message: str | None = None,
    ) -> str:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, run_mode, requested_by, metadata_json, message, created_at, updated_at)
                VALUES (?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (job_id, run_mode, requested_by, json.dumps(metadata), message, now, now),
            )

        self.append_audit_event(
            action="job_status_transition",
            status="queued",
            details={"job_id": job_id, "run_mode": run_mode, "requested_by": requested_by},
        )
        return job_id

    def update_job_status(self, job_id: str, status: str, message: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, message = COALESCE(?, message), updated_at = ?
                WHERE job_id = ?
                """,
                (status, message, now, job_id),
            )

        self.append_audit_event(
            action="job_status_transition",
            status=status,
            details={"job_id": job_id, "message": message},
        )

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, status, run_mode, requested_by, metadata_json, message, created_at, updated_at
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "job_id": row[0],
            "status": row[1],
            "run_mode": row[2],
            "requested_by": row[3],
            "metadata": json.loads(row[4]),
            "message": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def get_job_logs(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            # Look for auditing rows where the details_json contains '"job_id": "job-..."'
            # Note: SQLite JSON1 extension is available in Python 3.9+ but we can just LIKE it if we're careful.
            # Using LIKE since the audit events write `"job_id": "xxxx"` to details_json.
            like_pattern = f'%"{job_id}"%'
            rows = conn.execute(
                """
                SELECT id, action, status, details_json, created_at
                FROM audit_log
                WHERE details_json LIKE ?
                ORDER BY id ASC
                """,
                (like_pattern,),
            ).fetchall()

        # Double check parsing to ensure it's exactly the requested job.
        logs = []
        for row in rows:
            details = json.loads(row[3])
            if details.get("job_id") == job_id:
                logs.append({
                    "id": row[0],
                    "action": row[1],
                    "status": row[2],
                    "details": details,
                    "created_at": row[4],
                })
        return logs

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
            conn.execute(
                """
                INSERT INTO job_artifacts (job_id, artifact_type, path, md5, size_bytes, content_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, artifact_type, path, md5, size_bytes, content_type),
            )


    def list_job_artifacts(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT artifact_type, path, md5, size_bytes, content_type, created_at
                FROM job_artifacts
                WHERE job_id = ?
                ORDER BY id ASC
                """,
                (job_id,),
            ).fetchall()

        return [
            {
                "artifact_type": row[0],
                "path": row[1],
                "md5": row[2],
                "size_bytes": row[3],
                "content_type": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, status, run_mode, requested_by, metadata_json, message, created_at, updated_at
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return [
            {
                "job_id": row[0],
                "status": row[1],
                "run_mode": row[2],
                "requested_by": row[3],
                "metadata": json.loads(row[4]),
                "message": row[5],
                "created_at": row[6],
                "updated_at": row[7],
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
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_steps (job_id, step_id, name, status, input_data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, step_id) DO UPDATE SET
                    status = excluded.status,
                    input_data_json = COALESCE(excluded.input_data_json, job_steps.input_data_json),
                    updated_at = excluded.updated_at
                """,
                (job_id, step_id, name, status, json.dumps(input_data) if input_data else None, now, now),
            )

    def update_job_step(
        self,
        job_id: str,
        step_id: str,
        status: str,
        output_data: dict | None = None,
        is_manually_edited: bool = False,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE job_steps
                SET status = ?, output_data_json = COALESCE(?, output_data_json), 
                    is_manually_edited = ?, updated_at = ?
                WHERE job_id = ? AND step_id = ?
                """,
                (status, json.dumps(output_data) if output_data else None, 1 if is_manually_edited else 0, now, job_id, step_id),
            )

    def get_job_steps(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT step_id, name, status, input_data_json, output_data_json, is_manually_edited, created_at, updated_at
                FROM job_steps
                WHERE job_id = ?
                ORDER BY created_at ASC
                """,
                (job_id,),
            ).fetchall()

        return [
            {
                "step_id": row[0],
                "name": row[1],
                "status": row[2],
                "input_data": json.loads(row[3]) if row[3] else None,
                "output_data": json.loads(row[4]) if row[4] else None,
                "is_manually_edited": bool(row[5]),
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]

