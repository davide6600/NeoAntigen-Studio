from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


SKILL_METADATA = {
    "name": "pipeline_orchestrator",
    "capabilities": ["nextflow_orchestration", "snakemake_orchestration", "safe_dry_run", "provenance_capture"],
    "input_types": ["FASTQ", "BAM", "VCF", "HLA", "RNA"],
    "priority": 100,
    "safety_level": "high",
}


@dataclass
class OrchestrationPlan:
    engine: str
    command: list[str]
    dry_run: bool
    requires_human_approval: bool
    notes: str


@dataclass
class ProvenanceRecord:
    run_id: str
    engine: str
    workflow: str
    params: dict[str, str]
    command: list[str]
    started_at: str
    completed_at: str | None = None
    exit_code: int | None = None
    environment: dict[str, str] = field(default_factory=dict)


def check_environment(engine: str) -> tuple[bool, str]:
    """Return (True, binary_path) when the engine is available, else (False, error_hint)."""
    if engine not in {"nextflow", "snakemake"}:
        return False, f"Unsupported engine '{engine}'"
    path = shutil.which(engine)
    if path is None:
        hints = {
            "nextflow": "curl -s https://get.nextflow.io | bash  # or conda install -c bioconda nextflow",
            "snakemake": "pip install snakemake  # or conda install -c bioconda snakemake",
        }
        return False, f"'{engine}' not found in PATH. Install with: {hints[engine]}"
    return True, path


def build_plan(engine: str, workflow: str, params: dict[str, str], dry_run: bool = True) -> OrchestrationPlan:
    if engine not in {"nextflow", "snakemake"}:
        raise ValueError("Unsupported workflow engine")

    if engine == "nextflow":
        cmd = ["nextflow", "run", workflow]
        for key, value in sorted(params.items()):
            cmd.extend([f"--{key}", str(value)])
    else:
        cmd = ["snakemake", "--snakefile", workflow]
        for key, value in sorted(params.items()):
            cmd.extend(["--config", f"{key}={value}"])

    return OrchestrationPlan(
        engine=engine,
        command=cmd,
        dry_run=dry_run,
        requires_human_approval=not dry_run,
        notes="Orchestration only. No destructive actions are executed by this scaffold.",
    )


def run_plan(plan: OrchestrationPlan, provenance_dir: str = "runs") -> ProvenanceRecord:
    """
    Execute an orchestration plan and capture a provenance record.

    In ``dry_run=True`` mode (the default) no external process is spawned;
    a synthetic provenance record is written and returned so callers can test
    the full pipeline path without needing the workflow engine installed.

    For real execution the engine binary must be available in PATH.
    """
    run_id = uuid.uuid4().hex[:8]
    started = datetime.now(UTC).isoformat()
    workflow = plan.command[2] if len(plan.command) > 2 else "unknown"

    if plan.dry_run:
        record = ProvenanceRecord(
            run_id=f"dryrun-{run_id}",
            engine=plan.engine,
            workflow=workflow,
            params={},
            command=plan.command,
            started_at=started,
            completed_at=started,
            exit_code=0,
            environment={"mode": "dry_run"},
        )
        _write_provenance(record, provenance_dir)
        return record

    available, path_or_hint = check_environment(plan.engine)
    if not available:
        # Fall back gracefully as per Task 2 requirements, imitating a dry run.
        record = ProvenanceRecord(
            run_id=f"fallback-{run_id}",
            engine=plan.engine,
            workflow=workflow,
            params={},
            command=plan.command,
            started_at=started,
            completed_at=started,
            exit_code=0,
            environment={"mode": "fallback_no_engine_installed", "missing": path_or_hint},
        )
        _write_provenance(record, provenance_dir)
        return record

    record = ProvenanceRecord(
        run_id=run_id,
        engine=plan.engine,
        workflow=workflow,
        params={},
        command=plan.command,
        started_at=started,
        environment={"engine_path": path_or_hint},
    )

    try:
        result = subprocess.run(  # noqa: S603 — command constructed internally, not from user input
            plan.command,
            capture_output=True,
            text=True,
            timeout=3600,
        )
    except subprocess.TimeoutExpired as exc:
        record.completed_at = datetime.now(UTC).isoformat()
        record.exit_code = -1
        _write_provenance(record, provenance_dir)
        raise RuntimeError("Workflow timed out after 3600 seconds") from exc

    record.completed_at = datetime.now(UTC).isoformat()
    record.exit_code = result.returncode
    _write_provenance(record, provenance_dir)

    if result.returncode != 0:
        raise RuntimeError(
            f"Workflow exited with code {result.returncode}: {result.stderr[:500]}"
        )
    return record


def _write_provenance(record: ProvenanceRecord, provenance_dir: str) -> Path:
    target = Path(provenance_dir) / record.run_id / "provenance.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
    return target


def minimal_smoke_command() -> list[str]:
    return ["nextflow", "run", "pipelines/nextflow/smoke_test/main.nf"]
