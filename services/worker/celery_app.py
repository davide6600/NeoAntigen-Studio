from __future__ import annotations

import os

from celery import Celery

from services.worker.tasks import execute_job_task


BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery("neoantigen_worker", broker=BROKER_URL, backend=RESULT_BACKEND)


@celery_app.task(name="services.worker.tasks.execute_job_task")
def execute_job_task_wrapper(job_id: str, db_path: str = "agent/learnings/learnings.db") -> dict:
    return execute_job_task(job_id=job_id, db_path=db_path)
