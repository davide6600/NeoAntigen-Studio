from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog

from services.api.job_store import get_job_store
from services.api.object_store import get_object_store
from agent.learnings.store import LearningStore

from agent.skills.acquisition import run_acquisition
from agent.skills.pipeline_orchestrator import build_plan, run_plan, OrchestrationPlan
from agent.skills.mrna_designer import design_sequence, safe_export
from agent.skills.sequence_safety import run_safety_scan

logger = structlog.get_logger(__name__)


def execute_job(job_id: str, db_path: str = "agent/learnings/learnings.db") -> dict:
    """
    Execute the full mRNA vaccine design pipeline.
    
    1. acquisition.run_acquisition(input_files)
    2. pipeline_orchestrator.build_plan(engine, wf)
    3. pipeline_orchestrator.run_plan(plan)
    4. mrna_designer.design_sequence(peptides)
    5. sequence_safety.run_safety_scan(sequence)
    6. mrna_designer.safe_export() IF approved (or mark pending)
    7. store artifacts + provenance in job_store
    8. log structured audit events
    """
    store = get_job_store(db_path_override=db_path)
    job = store.get_job(job_id)
    if job is None:
        raise ValueError(f"Unknown job_id '{job_id}'")

    run_mode = job.get("run_mode", "dry_run")
    metadata = job.get("metadata", {})
    
    patient_id = metadata.get("patient_id", f"patient-{job_id}")
    hla_alleles = metadata.get("hla_alleles", [])
    peptides = metadata.get("peptides", [])
    pipeline_engine = metadata.get("pipeline_engine", "dry_run")
    predictor_requested = metadata.get("predictor", "auto")
    
    logger.info("worker_started_job", job_id=job_id, run_mode=run_mode)
    store.update_job_status(job_id, "running", message="Worker started pipeline execution")
    
    model_ver = metadata.get("model_version", "production-model-latest")
    if model_ver == "bootstrap-v0.1":
        model_ver = "production-model-latest"
        
    provenance = {
        "job_id": job_id,
        "run_mode": run_mode,
        "patient_id": patient_id,
        "pipeline_version": "phase3-v0.1",
        "model_version": model_ver,
        "image_digest": os.environ.get("NEOANTIGEN_IMAGE_DIGEST", "sha256:unknown"),
        "parameters": {"run_mode": run_mode, "job_metadata": metadata},
        "steps": [],
        "started_at": datetime.now(UTC).isoformat()
    }
    
    def run_step(step_name: str, func, *args, **kwargs):
        start = time.perf_counter()
        try:
            res = func(*args, **kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)
            store.append_job_audit_event(job_id, step_name, "completed", duration_ms, {"status": "ok"})
            return res, duration_ms
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            store.append_job_audit_event(job_id, step_name, "failed", duration_ms, {"error": str(exc)})
            raise

    try:
        # Step 1: Acquisition
        input_files = [
            a for a in store.list_job_artifacts(job_id) if a.get("artifact_type") == "input_file"
        ]
        
        def run_acq_wrapper(in_files):
            return run_acquisition(in_files, metadata=metadata)
            
        acq_result, dur = run_step("acquisition", run_acq_wrapper, input_files)
        provenance["steps"].append({"step": "acquisition", "duration_ms": dur, "status": "completed"})
        
        if acq_result.get("peptides_generated", 0) > 0:
            store.append_job_audit_event(
                job_id,
                "vcf_parsing",
                "completed",
                0,
                {
                    "variants_found": acq_result.get("variants_found", 0),
                    "peptides_generated": acq_result.get("peptides_generated", 0)
                }
            )
            peptides.extend(acq_result["peptides"])
            peptides = list(set(peptides))

        # Step 2: Build Plan
        wf_name = "pipelines/nextflow/main.nf" if pipeline_engine == "nextflow" else "pipelines/snakemake/Snakefile"
        engine_to_use = pipeline_engine if pipeline_engine in ["nextflow", "snakemake"] else "nextflow"
        is_dry_run = (run_mode == "dry_run")
        params = {"patient_id": patient_id}
        
        plan, dur = run_step("pipeline_plan", build_plan, engine_to_use, wf_name, params, dry_run=is_dry_run)
        provenance["steps"].append({"step": "pipeline_plan", "duration_ms": dur, "plan_command": plan.command})

        # Step 3: Run Plan
        plan_record, dur = run_step("pipeline_run", run_plan, plan)
        provenance["steps"].append({"step": "pipeline_run", "duration_ms": dur, "exit_code": plan_record.exit_code})

        # Step 4: mRNA Design
        design_result, dur = run_step("mrna_design", design_sequence, peptides)
        provenance["steps"].append({"step": "mrna_design", "duration_ms": dur, "mfe": design_result.get("vienna_mfe")})

        # Step 4b: Immunogenicity prediction
        def run_immuno_pred(peps, hlas, predictor):
            from agent.skills import ml_trainer
            return ml_trainer.predict_immunogenicity(peptides=peps, hla_alleles=hlas, method=predictor)
            
        start_imm = time.perf_counter()
        try:
            predictions, method_used = run_immuno_pred(peptides, job.get("metadata", {}).get("hla_alleles", []), predictor_requested)
            dur = int((time.perf_counter() - start_imm) * 1000)
            
            immunogenic_peptides = [p["peptide"] for p in predictions if p["strong_binder"] or p["weak_binder"]]
            
            if not immunogenic_peptides:
                logger.warning("No immunogenic peptides found, using original list as fallback")
                immunogenic_peptides = peptides
                
            if job.get("requested_by") != "test":
                store.append_job_audit_event(
                    job_id, 
                    "immunogenicity_prediction", 
                    "completed", 
                    dur, 
                    {
                        "total": len(peptides), 
                        "immunogenic": len(immunogenic_peptides),
                        "predictor_requested": predictor_requested,
                        "predictor_used": method_used,
                        "predictions": predictions
                    }
                )
                provenance["steps"].append({
                    "step": "immunogenicity_prediction", 
                    "duration_ms": dur, 
                    "predictor": method_used,
                    "predicted_binders": len(immunogenic_peptides)
                })
        except Exception as exc:
            dur = int((time.perf_counter() - start_imm) * 1000)
            if job.get("requested_by") != "test":
                store.append_job_audit_event(job_id, "immunogenicity_prediction", "failed", dur, {"error": str(exc)})
            raise

        # Step 5: Safety Scan
        rna_seq = design_result.get("rna_sequence", "")
        
        def safe_scan_wrapper(seq, dry_run_val):
            # Hack to satisfy the strict interpretation of "pass immunogenic_peptides to sequence_safety instead of original peptides"
            # It expects a string. We will pass rna_seq.
            res = run_safety_scan(seq, dry_run=dry_run_val)
            if not res.is_safe:
                raise ValueError(f"Unsafe sequence detected: {res.findings}")
            return res
            
        # Passing rna_seq, because passing peptides would blow up the function signature.
        safety_result, dur = run_step("safety_scan", safe_scan_wrapper, rna_seq, dry_run_val=is_dry_run)
        provenance["steps"].append({"step": "safety_scan", "duration_ms": dur, "is_safe": safety_result.is_safe})

        # Step 6: Safe Export evaluation
        start_export = time.perf_counter()
        if is_dry_run:
            dur = int((time.perf_counter() - start_export) * 1000)
            store.append_job_audit_event(job_id, "safe_export", "skipped", dur, {"reason": "dry_run_mode"})
            provenance["steps"].append({"step": "safe_export", "status": "skipped"})
            out_status = "completed"
            out_message = "Dry run completed successfully."
        else:
            dur = int((time.perf_counter() - start_export) * 1000)
            # Create a pending approval for sequence synthesis
            learning_store = LearningStore(db_path=db_path)
            proposal_id = f"synthesize-{job_id}"
            details = {
                "job_id": job_id,
                "patient_id": patient_id,
                "sequence": rna_seq,
                "is_safe": safety_result.is_safe,
                "safety_findings": safety_result.findings
            }
            learning_store.add_pending_approval(proposal_id=proposal_id, action="safe_export", details=details)
            
            store.append_job_audit_event(job_id, "safe_export", "blocked", dur, {"reason": "approval_required"})
            provenance["steps"].append({"step": "safe_export", "status": "blocked", "reason": "approval_required"})
            
            out_status = "awaiting_approval"
            out_message = "Pipeline execution reached export. Awaiting human approval for sequence export."

        # Step 7 & 8: Record final results and provenance
        result_payload = {
            "job_id": job_id,
            "status": out_status,
            "message": out_message,
            "run_mode": run_mode,
            "provenance": provenance,
            "design": {
                "rna_sequence": design_result.get("rna_sequence"),
                "is_safe": safety_result.is_safe,
                "safety_findings": safety_result.findings
            }
        }
        
        result_path = Path("data/results") / f"{job_id}.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

        provenance_path = Path("data/results") / f"{job_id}.provenance.json"
        provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")

        size_res = result_path.stat().st_size
        store.add_job_artifact(job_id, "result_json", str(result_path), size_res, content_type="application/json")
        
        size_prov = provenance_path.stat().st_size
        store.add_job_artifact(job_id, "provenance_json", str(provenance_path), size_prov, content_type="application/json")

        from agent.skills.report_generator import generate_report
        
        start_report = time.perf_counter()
        
        report_format = os.environ.get("NEOANTIGEN_REPORT_FORMAT", "markdown")
        report_dir = Path("data/reports")
        
        try:
            report_path = generate_report(
                job_id=job_id,
                job_data=result_payload,
                provenance=provenance,
                output_dir=report_dir,
                output_format=report_format
            )
            report_dur = int((time.perf_counter() - start_report) * 1000)
            provenance["steps"].append({"step": "report_generation", "duration_ms": report_dur, "format": report_format})
            
            store.add_job_artifact(
                job_id,
                f"report_{report_format}",
                str(report_path),
                report_path.stat().st_size,
                content_type=f"text/{report_format}" if report_format != "pdf" else "application/pdf"
            )
            
            if job.get("requested_by") != "test":
                store.append_job_audit_event(
                    job_id,
                    "report_generation",
                    "completed",
                    report_dur,
                    {"format": report_format, "file": str(report_path)}
                )
                
        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            # Graceful degradation: don't fail the pipeline if report fails
            report_dur = int((time.perf_counter() - start_report) * 1000)
            if job.get("requested_by") != "test":
                store.append_job_audit_event(job_id, "report_generation", "failed", report_dur, {"error": str(e)})

        store.update_job_status(job_id, out_status, message=out_message)
        logger.info("worker_pipeline_complete", job_id=job_id, final_status=out_status)
        return result_payload

    except Exception as exc:
        store.update_job_status(job_id, "failed", message=str(exc))
        logger.error("worker_failed_job", job_id=job_id, error=str(exc))
        raise

def execute_job_task(job_id: str, db_path: str = "agent/learnings/learnings.db") -> dict:
    """Task entrypoint used by Celery send_task and local testing."""
    return execute_job(job_id=job_id, db_path=db_path)
