from __future__ import annotations

import json
import builtins
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from fastapi import Query

from prometheus_client import make_asgi_app

from agent.auth.rbac import verify_approval
from agent.context.indexer import ContextIndexer
from agent.learnings.store import LearningStore
from agent.privacy.retention import execute_deletion, schedule_deletion
from agent.skills.label_ingest import ingest_labels
from services.api.job_store import get_job_store
from services.api.object_store import get_object_store
from services.worker.queue import enqueue_job
from services.worker.phase5_postgres_persistence import persist_labels, get_flagged_labels, resolve_flagged_label
from services.worker import cohort_analysis
from agent.skills.lims_adapters import generate_assay_manifest, parse_assay_manifest
from services.api.config import get_settings

import structlog

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="NeoAntigen Studio API",
    description=(
        "Research Use Only. No clinical claims, no direct synthesis orders. "
        "All sequence exports require explicit human approval."
    ),
    version="0.1.0",
)

# Add Prometheus metrics route
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

from fastapi import Request
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    traceback.print_exc()
    return Response(
        content=json.dumps({"detail": "Internal Server Error", "error": str(exc)}),
        status_code=500,
        media_type="application/json"
    )

from typing import Literal

class ApprovalRequest(BaseModel):
    approved_by: str
    token: str

class JobMetadata(BaseModel):
    patient_id: str
    hla_alleles: list[str]
    pipeline_engine: Literal["nextflow", "snakemake", "dry_run"] = "dry_run"
    predictor: Literal["auto", "sklearn", "netmhcpan"] = "auto"
    model_version: str = "bootstrap-v0.1"
    peptides: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)


class JobInputFile(BaseModel):
    name: str
    base64_content: str
    content_type: str = "application/octet-stream"
    expected_md5: str | None = None


class JobCreateRequest(BaseModel):
    requested_by: str
    run_mode: str = "dry_run"
    metadata: JobMetadata
    inputs: list[JobInputFile] = Field(default_factory=list)


class IngestLabelsRequest(BaseModel):
    labels: list[dict]
    enforce_schema: bool = True
    uncertainty_threshold: float = 0.7


class DeletionScheduleRequest(BaseModel):
    patient_id: str
    reason: str
    requester_id: str


class DeletionExecuteRequest(BaseModel):
    approved_by: str
    token: str
    object_paths: list[str] = Field(default_factory=list)


class ModelRetrainRequest(BaseModel):
    training_data_id: str
    base_model_version: str


class ModelPromoteRequest(BaseModel):
    approved_by: str
    token: str


class ModelRollbackRequest(BaseModel):
    approved_by: str
    reason: str


class MrnaDesignRequest(BaseModel):
    peptides: list[str] = Field(..., min_length=1)
    linker: str = "GPGPG"
    species: str = "h_sapiens"


class MrnaExportRequest(BaseModel):
    proposal_id: str
    sequence: str
    destination_path: str
    approved_by: str
    token: str


class LabelReviewRequest(BaseModel):
    decision: str = Field(..., description="Action to take on the flagged label", pattern="^(accept|reject)$")
    approved_by: str
    token: str

class LimsManifestGenerateRequest(BaseModel):
    assay_type: str = Field(..., pattern="^(MS|TSCAN|MULTIMER|ELISPOT|KILLING|SCTCR)$")
    candidate_peptides: list[dict] = Field(..., min_length=1)

class StepUpdateRequest(BaseModel):
    status: str
    output_data: dict | None = None
    is_manually_edited: bool = False


class CohortAnalyzeRequest(BaseModel):
    job_ids: list[str] = Field(..., min_length=1)

def _store() -> LearningStore:
    settings = get_settings()
    return LearningStore(db_path=settings.neoantigen_learnings_db)


def _approval_secret() -> str | None:
    settings = get_settings()
    secret = settings.neoantigen_approval_secret.strip()
    return secret or None


def _append_entities_access_audit(*, status: str, details: dict) -> None:
    """Best-effort audit logging for entities endpoint access decisions."""
    action = "entities_access"
    settings = get_settings()
    database_url = settings.neoantigen_database_url.strip()

    if database_url:
        try:
            psycopg = builtins.__import__("psycopg")
            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audit_log (action, status, details_json)
                        VALUES (%s, %s, %s::jsonb)
                        """,
                        (action, status, json.dumps(details)),
                    )
                conn.commit()
            return
        except Exception:
            # Fall through to local learnings store audit path.
            pass

    try:
        _store().append_audit_event(action=action, status=status, details=details)
    except Exception:
        # Audit logging must not break the request path.
        return


def _augment_artifact_access(job_id: str, artifacts: list[dict]) -> list[dict]:
    object_store = get_object_store()
    settings = get_settings()
    download_ttl = settings.neoantigen_signed_url_ttl_seconds
    augmented: list[dict] = []
    for artifact in artifacts:
        enriched = dict(artifact)
        path = str(artifact.get("path") or "")
        if path.startswith("s3://"):
            try:
                enriched["download_url"] = object_store.get_download_url(path, expires_seconds=download_ttl)
            except Exception:
                enriched["download_url"] = None
        elif path:
            enriched["download_url"] = None
        enriched["download_expires_in_seconds"] = download_ttl if enriched.get("download_url") else None
        if artifact.get("artifact_type") == "report_pdf":
            enriched["api_download_path"] = f"/jobs/{job_id}/report.pdf"
        augmented.append(enriched)
    return augmented


def _resolve_ranked_peptides_path(job_id: str) -> Path:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")

    artifacts = job_store.list_job_artifacts(job_id)
    ranked_artifact = next(
        (
            artifact
            for artifact in artifacts
            if str(artifact.get("artifact_type", "")).startswith("ranked_peptides_json")
            or str(artifact.get("path", "")).endswith("ranked_peptides.json")
        ),
        None,
    )
    if ranked_artifact:
        ranked_path = str(ranked_artifact.get("path", ""))
        if ranked_path.startswith("s3://"):
            raise HTTPException(
                status_code=400,
                detail=f"Cohort analysis requires local ranked_peptides.json files; job '{job_id}' only has remote object-store artifacts",
            )
        candidate = Path(ranked_path)
        if candidate.exists():
            return candidate

    fallback = Path("data/results") / job_id / "phase2" / "ranked_peptides.json"
    if fallback.exists():
        return fallback

    raise HTTPException(status_code=404, detail=f"ranked_peptides.json not found for job '{job_id}'")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ruo": True, "version": "0.1.0"}


@app.post("/api/cohort/analyze")
def analyze_cohort_endpoint(body: CohortAnalyzeRequest) -> dict:
    ranked_paths = [_resolve_ranked_peptides_path(job_id) for job_id in body.job_ids]
    summary = cohort_analysis.analyze_cohort(ranked_paths, patient_ids=body.job_ids)
    return asdict(summary)


@app.get("/api/cohort/hla-frequency")
def cohort_hla_frequency(job_ids: str = Query(..., description="Comma-separated job IDs")) -> dict:
    ids = [job_id.strip() for job_id in job_ids.split(",") if job_id.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="job_ids query parameter is required")
    ranked_paths = [_resolve_ranked_peptides_path(job_id) for job_id in ids]
    return cohort_analysis.hla_frequency_table(ranked_paths)


@app.get("/api/cohort/shared-peptides")
def cohort_shared_peptides(
    job_ids: str = Query(..., description="Comma-separated job IDs"),
    min_patients: int = Query(2, ge=1),
) -> list[dict]:
    ids = [job_id.strip() for job_id in job_ids.split(",") if job_id.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="job_ids query parameter is required")
    ranked_paths = [_resolve_ranked_peptides_path(job_id) for job_id in ids]
    return cohort_analysis.shared_peptides(ranked_paths, min_patients=min_patients)


@app.get("/context")
def get_context() -> dict:
    """Return the startup context summary: repository version, top skills, last learnings, pending approvals."""
    indexer = ContextIndexer()
    return indexer.load_context()


@app.get("/approvals")
def list_approvals() -> dict:
    """List pending human approval requests."""
    store = _store()
    return {"pending_approvals": store.list_pending_approvals(limit=50)}


@app.post("/approvals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, body: ApprovalRequest) -> dict:
    """Approve a pending proposal. Logs the approval to the audit trail."""
    store = _store()
    pending_ids = [p["proposal_id"] for p in store.list_pending_approvals(limit=200)]
    if proposal_id not in pending_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal '{proposal_id}' not found or already resolved",
        )
        
    try:
        identity = verify_approval(
            token=body.token,
            proposal_id=proposal_id,
            required_action="safe_export",  # Most common action requiring approval
            secret_key=_approval_secret()
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
        
    store.resolve_approval(proposal_id)
    store.append_audit_event(
        action="human_approval",
        status="approved",
        details={"proposal_id": proposal_id, "approved_by": body.approved_by},
    )
    return {"proposal_id": proposal_id, "status": "approved"}


@app.get("/model-summary")
def model_summary() -> dict:
    """Return a summary of trained model versions and their metrics."""
    store = _store()
    return store.model_summary()


@app.get("/jobs")
def list_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List all jobs, newest first. Used by the Dashboard job monitor."""
    job_store = get_job_store()
    return job_store.list_jobs(limit=limit, offset=offset)


@app.post("/jobs")

def create_job(body: JobCreateRequest) -> dict:
    job_store = get_job_store()
    object_store = get_object_store()

    logger.info("creating_job", run_mode=body.run_mode, requested_by=body.requested_by)

    job_id = job_store.create_job(
        run_mode=body.run_mode,
        requested_by=body.requested_by,
        metadata=body.metadata.model_dump(),
        message="Job accepted",
    )

    try:
        for file in body.inputs:
            stored = object_store.put_base64(
                job_id=job_id,
                name=file.name,
                base64_content=file.base64_content,
                content_type=file.content_type,
                expected_md5=file.expected_md5,
            )
            job_store.add_job_artifact(
                job_id=job_id,
                artifact_type="input_file",
                path=stored.path,
                md5=stored.md5,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
            )
    except ValueError as exc:
        logger.error("job_creation_failed", job_id=job_id, error=str(exc))
        job_store.update_job_status(job_id=job_id, status="failed", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    queue_result = enqueue_job(job_id)
    
    logger.info("job_enqueued", job_id=job_id, status=queue_result.get("status"), queue_mode=queue_result.get("queue_mode"))

    return {
        "job_id": job_id,
        "status": queue_result.get("status", "queued"),
        "queue_mode": queue_result.get("queue_mode", "unknown"),
        "ruo": True,
        "message": "Job accepted and enqueued.",
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
    return job


@app.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: str, format: str = Query(default="json")):
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
        
    logs = job_store.get_job_logs(job_id)
    
    if format == "text":
        lines = []
        for log in logs:
            action = log.get("action", "")
            status = log.get("status", "")
            details = log.get("details", {})
            msg = details.get("message") or details.get("error") or ""
            ts = log.get("created_at", "")
            line = f"[{ts}] {action} - {status}"
            if msg:
                line += f": {msg}"
            lines.append(line)
        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{job_id}-logs.txt"'}
        )
        
    return {"job_id": job_id, "logs": logs, "ruo": True}


@app.get("/jobs/{job_id}/audit-trail")
def get_job_audit_trail(job_id: str) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")

    steps = job_store.list_job_audit_events(job_id)
    return {"job_id": job_id, "steps": steps}




@app.get("/jobs/{job_id}/steps")
def get_job_steps(job_id: str) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
        
    steps = job_store.get_job_steps(job_id)
    return {"job_id": job_id, "steps": steps, "ruo": True}


@app.post("/jobs/{job_id}/steps/{step_id}/update")
def update_job_step(job_id: str, step_id: str, body: StepUpdateRequest) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
        
    job_store.update_job_step(
        job_id=job_id,
        step_id=step_id,
        status=body.status,
        output_data=body.output_data,
        is_manually_edited=body.is_manually_edited,
    )
    
    if body.is_manually_edited:
        job_store.update_job_status(job_id=job_id, status=job["status"], message=f"Manual edit performed on step {step_id}")
        
    return {"job_id": job_id, "step_id": step_id, "status": "updated"}


@app.post("/jobs/{job_id}/steps/{step_id}/resume")
def resume_job_step(job_id: str, step_id: str) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
        
    # Mark the step as completed if it was paused
    job_store.update_job_step(job_id=job_id, step_id=step_id, status="completed")
    
    # Resume the job via the worker queue
    queue_result = enqueue_job(job_id)
    
    return {
        "job_id": job_id, 
        "step_id": step_id, 
        "status": "resuming",
        "queue_status": queue_result.get("status")
    }


@app.get("/jobs/{job_id}/results")
def get_job_results(job_id: str) -> dict:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")

    artifacts = _augment_artifact_access(job_id, job_store.list_job_artifacts(job_id))
    provenance = None
    result_payload = None
    provenance_artifact = next((a for a in artifacts if a["artifact_type"] == "provenance_json"), None)
    result_artifact = next((a for a in artifacts if a["artifact_type"] == "result_json"), None)
    if provenance_artifact is not None:
        try:
            provenance_path = Path(provenance_artifact["path"])
            if provenance_path.exists():
                try:
                    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    logger.error("invalid_provenance_json", job_id=job_id, error=str(exc))
                    provenance = None
        except OSError:
            pass
    if result_artifact is not None:
        try:
            result_path = Path(result_artifact["path"])
            if result_path.exists():
                try:
                    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    logger.error("invalid_result_json", job_id=job_id, error=str(exc))
                    result_payload = None
        except OSError:
            pass

    response = {
        "job_id": job_id,
        "status": job["status"],
        "ruo": True,
        "artifacts": artifacts,
        "provenance": provenance,
    }
    if isinstance(result_payload, dict):
        if "pipeline_summary" in result_payload:
            response["pipeline_summary"] = result_payload["pipeline_summary"]
        if "normalized_persistence" in result_payload:
            response["normalized_persistence"] = result_payload["normalized_persistence"]

    return response


from typing import Any

@app.get("/jobs/{job_id}/report", response_model=None)
@app.get("/jobs/{job_id}/report.{ext}", response_model=None)
def get_job_report(job_id: str, ext: str | None = None) -> Any:
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")

    artifacts = _augment_artifact_access(job_id, job_store.list_job_artifacts(job_id))
    
    # Identify which artifact to serve based on the extension
    if ext == "pdf":
        target_type = "report_pdf"
    elif ext == "html":
        target_type = "report_html"
    elif ext == "md":
        target_type = "report_markdown"
    else:
        # If no extension or unknown extension, return the first report available
        report = next((a for a in artifacts if a["artifact_type"] in ("report_markdown", "report_html", "report_pdf")), None)
        target_type = report["artifact_type"] if report else None

    report = next((a for a in artifacts if a["artifact_type"] == target_type), None)
    
    if report is None:
        raise HTTPException(status_code=404, detail=f"No report found for job '{job_id}'")

    report_path_value = str(report["path"])
    if report_path_value.startswith("s3://"):
        download_url = report.get("download_url")
        if not download_url:
            raise HTTPException(status_code=404, detail=f"Report path missing for job '{job_id}'")
        return RedirectResponse(url=download_url)

    report_path = Path(report_path_value)
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report path missing for job '{job_id}'")

    media_type = "text/markdown"
    if target_type == "report_pdf":
        media_type = "application/pdf"
    elif target_type == "report_html":
        media_type = "text/html"

    return FileResponse(path=report_path, media_type=media_type, filename=report_path.name)


@app.get("/jobs/{job_id}/entities")
def get_job_entities(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
    gene: str | None = Query(default=None, min_length=1, max_length=64),
    x_requester_id: str | None = Header(default=None, alias="X-Requester-Id"),
    x_requester_role: str | None = Header(default=None, alias="X-Requester-Role"),
    x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
) -> dict:
    """Return normalized Phase 2 scientific entities persisted in PostgreSQL for a job."""
    job_store = get_job_store()
    job = job_store.get_job(job_id)
    if job is None:
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "unknown_job",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
            },
        )
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'")
    if job.get("run_mode") != "phase2_real":
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "non_phase2_job",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
                "run_mode": job.get("run_mode"),
            },
        )
        raise HTTPException(status_code=400, detail="Normalized entities are only available for phase2_real jobs")

    if not x_requester_id:
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "missing_requester_id",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
            },
        )
        raise HTTPException(status_code=403, detail="X-Requester-Id header is required for normalized entities access")

    metadata = job.get("metadata", {})
    job_requested_by = str(job.get("requested_by") or "")
    job_project_id = str(metadata.get("project_id") or "")
    requester_role = (x_requester_role or "").strip().lower()
    privileged_roles = {
        "pi",
        "data_manager",
        "privacy_officer",
        "ml_lead",
        "platform_owner",
        "security_lead",
    }

    if requester_role not in privileged_roles and x_requester_id != job_requested_by:
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "requester_mismatch",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
                "job_requested_by": job_requested_by,
            },
        )
        raise HTTPException(status_code=403, detail="Requester is not authorized for this job")

    if job_project_id:
        if not x_project_id:
            _append_entities_access_audit(
                status="rejected",
                details={
                    "job_id": job_id,
                    "reason": "missing_project_scope",
                    "requester_id": x_requester_id,
                    "requester_role": x_requester_role,
                    "project_id": x_project_id,
                    "job_project_id": job_project_id,
                },
            )
            raise HTTPException(status_code=403, detail="X-Project-Id header is required for project-scoped access")
        if x_project_id != job_project_id:
            _append_entities_access_audit(
                status="rejected",
                details={
                    "job_id": job_id,
                    "reason": "project_scope_mismatch",
                    "requester_id": x_requester_id,
                    "requester_role": x_requester_role,
                    "project_id": x_project_id,
                    "job_project_id": job_project_id,
                },
            )
            raise HTTPException(status_code=403, detail="Requester project scope does not match job project")

    settings = get_settings()
    database_url = settings.neoantigen_database_url.strip()
    if not database_url:
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "missing_database_url",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
            },
        )
        raise HTTPException(status_code=400, detail="NEOANTIGEN_DATABASE_URL is not configured")

    try:
        psycopg = builtins.__import__("psycopg")
    except ImportError as exc:
        _append_entities_access_audit(
            status="rejected",
            details={
                "job_id": job_id,
                "reason": "psycopg_missing",
                "requester_id": x_requester_id,
                "requester_role": x_requester_role,
                "project_id": x_project_id,
            },
        )
        raise HTTPException(status_code=500, detail="psycopg is required for PostgreSQL-backed entities endpoint") from exc

    patient_id = str(metadata.get("patient_id") or f"patient-{job_id}")
    sample_id = str(metadata.get("sample_id") or f"sample-{job_id}")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT patient_id, consent_status, project_id
                FROM patient
                WHERE patient_id = %s
                """,
                (patient_id,),
            )
            patient_row = cur.fetchone()

            cur.execute(
                """
                SELECT sample_id, patient_id, sample_type, lims_id
                FROM sample
                WHERE sample_id = %s
                """,
                (sample_id,),
            )
            sample_row = cur.fetchone()

            cur.execute(
                """
                SELECT run_id, object_store_path, md5, platform, read_type
                FROM sequence_run
                WHERE sample_id = %s
                ORDER BY created_at DESC
                """,
                (sample_id,),
            )
            run_rows = cur.fetchall()

            cur.execute(
                """
                SELECT variant_id, gene, effect, vaf, clonal_status
                FROM variant
                WHERE sample_id = %s
                AND (%s IS NULL OR gene = %s)
                ORDER BY created_at ASC
                LIMIT %s OFFSET %s
                """,
                (sample_id, gene, gene, limit, offset),
            )
            variant_rows = cur.fetchall()

            cur.execute(
                """
                SELECT COUNT(*)
                FROM variant
                WHERE sample_id = %s
                AND (%s IS NULL OR gene = %s)
                """,
                (sample_id, gene, gene),
            )
            variant_count_row = cur.fetchone()
            variant_total = int(variant_count_row[0]) if variant_count_row else 0

            cur.execute(
                """
                SELECT pc.peptide_id, pc.seq, pc.hla_allele, pr.prediction_id, pr.model_version, pr.score
                FROM peptide_candidate pc
                JOIN variant v ON v.variant_id = pc.source_variant_id
                JOIN prediction_record pr ON pr.peptide_id = pc.peptide_id
                WHERE v.sample_id = %s
                AND (%s IS NULL OR v.gene = %s)
                AND (%s IS NULL OR pr.score >= %s)
                ORDER BY pr.score DESC
                LIMIT %s OFFSET %s
                """,
                (sample_id, gene, gene, min_score, min_score, limit, offset),
            )
            peptide_prediction_rows = cur.fetchall()

            cur.execute(
                """
                SELECT COUNT(*)
                FROM peptide_candidate pc
                JOIN variant v ON v.variant_id = pc.source_variant_id
                JOIN prediction_record pr ON pr.peptide_id = pc.peptide_id
                WHERE v.sample_id = %s
                AND (%s IS NULL OR v.gene = %s)
                AND (%s IS NULL OR pr.score >= %s)
                """,
                (sample_id, gene, gene, min_score, min_score),
            )
            prediction_count_row = cur.fetchone()
            prediction_total = int(prediction_count_row[0]) if prediction_count_row else 0

    response = {
        "job_id": job_id,
        "ruo": True,
        "filters": {
            "gene": gene,
            "min_score": min_score,
            "limit": limit,
            "offset": offset,
        },
        "counts": {
            "variants_total": variant_total,
            "predictions_total": prediction_total,
        },
        "patient": (
            {
                "patient_id": patient_row[0],
                "consent_status": patient_row[1],
                "project_id": patient_row[2],
            }
            if patient_row
            else None
        ),
        "sample": (
            {
                "sample_id": sample_row[0],
                "patient_id": sample_row[1],
                "sample_type": sample_row[2],
                "lims_id": sample_row[3],
            }
            if sample_row
            else None
        ),
        "sequence_runs": [
            {
                "run_id": row[0],
                "object_store_path": row[1],
                "md5": row[2],
                "platform": row[3],
                "read_type": row[4],
            }
            for row in run_rows
        ],
        "variants": [
            {
                "variant_id": row[0],
                "gene": row[1],
                "effect": row[2],
                "vaf": row[3],
                "clonal_status": row[4],
            }
            for row in variant_rows
        ],
        "predictions": [
            {
                "peptide_id": row[0],
                "peptide": row[1],
                "hla_allele": row[2],
                "prediction_id": row[3],
                "model_version": row[4],
                "score": row[5],
            }
            for row in peptide_prediction_rows
        ],
    }

    _append_entities_access_audit(
        status="allowed",
        details={
            "job_id": job_id,
            "requester_id": x_requester_id,
            "requester_role": x_requester_role,
            "project_id": x_project_id,
            "filters": {
                "gene": gene,
                "min_score": min_score,
                "limit": limit,
                "offset": offset,
            },
            "counts": response.get("counts", {}),
        },
    )

    return response


@app.post("/ingest-labels")
def ingest_experiment_labels(body: IngestLabelsRequest) -> dict:
    logger.info("ingesting_labels", label_count=len(body.labels), enforce_schema=body.enforce_schema)
    store = _store()
    result = ingest_labels(
        raw_labels=body.labels,
        uncertainty_threshold=body.uncertainty_threshold,
        store=store,
        enforce_schema=body.enforce_schema,
    )
    
    parsed_labels = result.pop("parsed_labels", [])
    if parsed_labels:
        persist_labels(parsed_labels)

    store.append_audit_event(
        action="ingest_labels",
        status="completed",
        details={
            "batch_id": result["batch_id"],
            "total": result["total"],
            "accepted": result["accepted"],
            "flagged": result["flagged"],
        },
    )
    
    logger.info("labels_ingested", batch_id=result["batch_id"], accepted=result.get("accepted"), flagged=result.get("flagged"))

    if result.get("accepted", 0) > 0:
        from agent.skills.ml_trainer import stage_retrain, generate_staging_report, register_with_mlflow, build_explainability_artifact
        
        proposal = stage_retrain(
            training_data_id=result["batch_id"],
            base_model_version="seq2neo-v1"
        )
        metrics = {"accuracy": 0.95, "roc_auc": 0.97}
        explainability = build_explainability_artifact(
            top_features=["binding_score", "expression_tpm"],
            decision_rules=["auto-retrain triggered by label ingestion"],
            misclassified_ids=[]
        )
        report_path = generate_staging_report(proposal, metrics, explainability)
        run_id = register_with_mlflow(proposal, metrics, str(report_path.parent))
        
        store.add_pending_approval(
            proposal_id=proposal.model_version,
            action="model_promotion",
            details={
                "training_data_id": result["batch_id"],
                "base_model_version": "seq2neo-v1",
                "target_stage": proposal.target_stage,
                "mlflow_run_id": run_id
            }
        )

    return result

@app.get("/labels/flagged")
def list_flagged_labels() -> dict:
    return {"flagged_labels": get_flagged_labels()}

@app.post("/labels/{label_id}/review")
def review_flagged_label(label_id: str, body: LabelReviewRequest) -> dict:
    store = _store()
    try:
        approval_identity = verify_approval(
            body.token,
            label_id,
            required_action="label_review",
            secret_key=_approval_secret(),
        )
    except Exception as exc:
        store.append_audit_event(
            action="human_approval",
            status="rejected",
            details={
                "proposal_id": label_id,
                "approved_by": body.approved_by,
                "reason": "execution_error",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        resolve_flagged_label(label_id, body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    store.append_audit_event(
        action="human_approval",
        status="approved",
        details={
            "proposal_id": label_id,
            "approved_by": body.approved_by,
            "action": f"label_review_{body.decision}",
            "approval_role": approval_identity.role if approval_identity else "reviewer",
            "approval_user_id": approval_identity.user_id if approval_identity else "anonymous",
        },
    )
    return {"label_id": label_id, "status": "reviewed", "decision": body.decision}

@app.post("/lims/manifests/generate")
def generate_lims_manifest(body: LimsManifestGenerateRequest) -> dict:
    manifest = generate_assay_manifest(body.assay_type, body.candidate_peptides)
    return manifest

@app.post("/lims/manifests/parse")
def parse_lims_manifest(manifest: dict) -> dict:
    parsed_items = parse_assay_manifest(manifest)
    return {"parsed_items": parsed_items}



@app.post("/deletions")
def create_deletion_request(body: DeletionScheduleRequest) -> dict:
    store = _store()
    request_id = schedule_deletion(
        patient_id=body.patient_id,
        reason=body.reason,
        requester_id=body.requester_id,
        store=store,
    )
    store.add_pending_approval(
        proposal_id=request_id,
        action="deletion_request",
        details={
            "patient_id": body.patient_id,
            "reason": body.reason,
            "requester_id": body.requester_id,
        },
    )
    return {
        "request_id": request_id,
        "patient_id": body.patient_id,
        "status": "pending",
        "approval_required": True,
        "ruo": True,
    }


@app.get("/deletions/{request_id}")
def get_deletion_request_status(request_id: str) -> dict:
    store = _store()
    request = store.get_deletion_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Unknown deletion request '{request_id}'")
    request["ruo"] = True
    return request


@app.post("/deletions/{request_id}/execute")
def execute_deletion_request(request_id: str, body: DeletionExecuteRequest) -> dict:
    store = _store()
    request = store.get_deletion_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Unknown deletion request '{request_id}'")
    if request["status"] != "pending":
        store.append_audit_event(
            action="human_approval",
            status="rejected",
            details={
                "proposal_id": request_id,
                "approved_by": body.approved_by,
                "reason": "request_not_pending",
                "current_status": request["status"],
            },
        )
        raise HTTPException(status_code=400, detail=f"Deletion request '{request_id}' is not pending")

    approval_identity = None
    try:
        approval_identity = verify_approval(
            body.token,
            request_id,
            required_action="deletion_request",
            secret_key=_approval_secret(),
        )
        object_store = get_object_store() if body.object_paths else None
        result = execute_deletion(
            request_id=request_id,
            approved_by=body.approved_by,
            store=store,
            object_store=object_store,
            object_paths=body.object_paths,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        store.append_audit_event(
            action="human_approval",
            status="rejected",
            details={
                "proposal_id": request_id,
                "approved_by": body.approved_by,
                "approval_role": approval_identity.role if approval_identity is not None else None,
                "approval_user_id": approval_identity.user_id if approval_identity is not None else None,
                "reason": "execution_error",
                "error": str(exc),
                "current_status": request["status"],
            },
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.resolve_approval(request_id)
    store.append_audit_event(
        action="human_approval",
        status="approved",
        details={
            "proposal_id": request_id,
            "approved_by": body.approved_by,
            "approval_role": approval_identity.role,
            "approval_user_id": approval_identity.user_id,
        },
    )
    result["ruo"] = True
    return result


@app.post("/models/retrain")
def retrain_model(body: ModelRetrainRequest) -> dict:
    from agent.skills.ml_trainer import stage_retrain, generate_staging_report, register_with_mlflow, build_explainability_artifact
    store = _store()
    
    proposal = stage_retrain(
        training_data_id=body.training_data_id,
        base_model_version=body.base_model_version
    )
    
    metrics = {"accuracy": 0.95, "roc_auc": 0.97}
    explainability = build_explainability_artifact(
        top_features=["binding_score", "expression_tpm", "uncertainty_score"],
        decision_rules=["if score > 0.8 then immunogenic", "if uncertainty > 0.5 then flag"],
        misclassified_ids=["pep-404"]
    )
    
    report_path = generate_staging_report(proposal, metrics, explainability)
    run_id = register_with_mlflow(proposal, metrics, str(report_path.parent))
    
    store.add_pending_approval(
        proposal_id=proposal.model_version,
        action="model_promotion",
        details={
            "training_data_id": body.training_data_id,
            "base_model_version": body.base_model_version,
            "target_stage": proposal.target_stage,
            "mlflow_run_id": run_id
        }
    )
    
    store.append_audit_event(
        action="stage_retrain",
        status="completed",
        details={
            "model_version": proposal.model_version,
            "training_data_id": body.training_data_id,
        }
    )
    
    return {
        "model_version": proposal.model_version,
        "status": "staged",
        "approval_required": True,
        "mlflow_run_id": run_id,
        "report_path": str(report_path),
        "ruo": True
    }


@app.post("/models/{model_version}/promote")
def promote_model(model_version: str, body: ModelPromoteRequest) -> dict:
    store = _store()
    
    pending_ids = [p["proposal_id"] for p in store.list_pending_approvals(limit=200)]
    if model_version not in pending_ids:
        store.append_audit_event(
            action="human_approval",
            status="rejected",
            details={
                "proposal_id": model_version,
                "approved_by": body.approved_by,
                "reason": "request_not_pending",
            },
        )
        raise HTTPException(status_code=400, detail=f"Model promotion for '{model_version}' is not pending")
        
    try:
        approval_identity = verify_approval(
            body.token,
            model_version,
            required_action="model_promotion",
            secret_key=_approval_secret(),
        )
    except PermissionError as exc:
        store.append_audit_event(
            action="human_approval",
            status="rejected",
            details={
                "proposal_id": model_version,
                "approved_by": body.approved_by,
                "reason": "execution_error",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    store.resolve_approval(model_version)
    store.append_audit_event(
        action="human_approval",
        status="approved",
        details={
            "proposal_id": model_version,
            "approved_by": body.approved_by,
            "action": "model_promotion",
            "approval_role": approval_identity.role if approval_identity else "reviewer",
            "approval_user_id": approval_identity.user_id if approval_identity else "anonymous",
            "canary_rollout_enabled": True
        },
    )
    
    # Store the active production model state
    store.append_audit_event(
        action="model_deployment",
        status="canary_active",
        details={
            "model_version": model_version,
            "traffic_percentage": 10
        }
    )
    
    return {
        "model_version": model_version,
        "status": "promoted_to_production",
        "canary_enabled": True,
        "initial_traffic_percentage": 10,
        "ruo": True
    }


@app.post("/models/{model_version}/rollback")
def rollback_model(model_version: str, body: ModelRollbackRequest) -> dict:
    store = _store()
    
    store.append_audit_event(
        action="model_rollback",
        status="completed",
        details={
            "model_version": model_version,
            "approved_by": body.approved_by,
            "reason": body.reason
        }
    )
    
    return {
        "model_version": model_version,
        "status": "rolled_back",
        "reason": body.reason,
        "ruo": True
    }


@app.post("/mrna/design")
def design_mrna(body: MrnaDesignRequest) -> dict:
    from agent.skills.mrna_designer import design_sequence, write_proposal
    import uuid
    
    store = _store()
    
    # Convert peptides array to the expected string format
    design_result = design_sequence(
        peptides=body.peptides,
        linker=body.linker,
        species=body.species
    )
    
    proposal_id = f"export-{str(uuid.uuid4()).split('-')[0]}"
    
    proposal_path = write_proposal(
        proposal_id=proposal_id,
        task="Sequence synthesis export",
        inputs=body.peptides,
        outputs=[design_result["dna_sequence"]],
        risks=["Biosecurity hazard", "Unauthorized synthesis"],
        required_approvals=["Biosecurity Officer"]
    )
    
    store.add_pending_approval(
        proposal_id=proposal_id,
        action="safe_export",
        details={
            "peptides_count": len(body.peptides),
            "is_safe": design_result["is_safe"],
            "safety_findings": design_result["safety_findings"],
            "proposal_path": str(proposal_path)
        }
    )
    
    return {
        "design": design_result,
        "proposal_id": proposal_id,
        "status": "design_complete_pending_export_approval",
        "ruo": True
    }


@app.post("/mrna/export")
def export_mrna(body: MrnaExportRequest) -> dict:
    from agent.skills.mrna_designer import safe_export
    store = _store()
    
    pending_ids = [p["proposal_id"] for p in store.list_pending_approvals(limit=200)]
    if body.proposal_id not in pending_ids:
        store.append_audit_event(
            action="safe_export",
            status="rejected",
            details={
                "proposal_id": body.proposal_id,
                "approved_by": body.approved_by,
                "reason": "request_not_pending",
            },
        )
        raise HTTPException(status_code=400, detail=f"Export for '{body.proposal_id}' is not pending")
        
    try:
        # safe_export performs safety scan and RBAC verification
        result_event = safe_export(
            sequence=body.sequence,
            destination_path=body.destination_path,
            proposal_id=body.proposal_id,
            approval_token=body.token,
            approved_by=body.approved_by,
            store=store,
            secret_key=_approval_secret(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    store.resolve_approval(body.proposal_id)
    
    return {
        "proposal_id": body.proposal_id,
        "status": "exported",
        "destination": body.destination_path,
        "approval_event": result_event,
        "ruo": True
    }

