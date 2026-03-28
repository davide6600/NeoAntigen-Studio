from __future__ import annotations

import os
import socket
import structlog

from services.worker.tasks import execute_job

logger = structlog.get_logger(__name__)


def enqueue_job(job_id: str, db_path: str | None = None) -> dict:
    """Queue scaffold: executes synchronously as a safe local fallback.

    This keeps API contracts stable while Celery/Redis wiring is introduced.
    """
    resolved_path = db_path or os.getenv("NEOANTIGEN_LEARNINGS_DB", "agent/learnings/learnings.db")
    broker_url = os.getenv("CELERY_BROKER_URL", "").strip()

    # Prefer broker-based queueing when Celery is configured, otherwise use local fallback.
    if broker_url:
        try:
            from celery import Celery

            app = Celery("neoantigen_worker", broker=broker_url, backend=os.getenv("CELERY_RESULT_BACKEND", broker_url))
            app.send_task("services.worker.tasks.execute_job_task", args=[job_id, resolved_path])
            return {
                "job_id": job_id,
                "status": "queued",
                "queue_mode": "celery",
            }
        except (ConnectionRefusedError, OSError, socket.error) as exc:
            # Preserve operational continuity in bootstrap mode when broker/Celery is unavailable.
            logger.warning("celery_broker_unavailable_fallback", error=str(exc))
        except Exception as exc:
            logger.exception("celery_dispatch_failed", error=str(exc))
            raise

    try:
        result = execute_job(job_id=job_id, db_path=resolved_path)
        return {
            "job_id": job_id,
            "status": "started_locally",
            "result_preview": result,
            "queue_mode": "local_fallback",
        }
    except Exception as exc:
        logger.exception("local_fallback_failed", error=str(exc))
        return {
            "job_id": job_id,
            "status": "failed_locally",
            "error": str(exc),
            "queue_mode": "local_fallback",
        }
