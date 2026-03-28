from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Any

import jsonschema
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.learnings.store import LearningStore


SKILL_METADATA = {
    "name": "label_ingest",
    "capabilities": ["experiment_label_validation", "json_schema_validation", "qc_rule_check", "acquisition_logging"],
    "input_types": ["LABEL", "JSON"],
    "priority": 90,
    "safety_level": "medium",
}

_SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "experiment_label.json"
_CACHED_SCHEMA: dict | None = None


def _load_schema() -> dict:
    global _CACHED_SCHEMA  # noqa: PLW0603
    if _CACHED_SCHEMA is None:
        if _SCHEMA_PATH.exists():
            _CACHED_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        else:
            _CACHED_SCHEMA = {}
    return _CACHED_SCHEMA


def validate_against_schema(raw: dict) -> list[str]:
    """Validate a raw label dict against the JSON schema. Returns a list of error messages."""
    schema = _load_schema()
    if not schema:
        return []
    errors: list[str] = []
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(raw), key=lambda e: e.path):
        errors.append(f"{'.'.join(str(p) for p in error.path) or 'root'}: {error.message}")
    return errors


class ExperimentLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_id: str
    peptide_id: str
    assay_type: Literal["MS", "TSCAN", "MULTIMER", "ELISPOT", "KILLING", "SCTCR"]
    assay_id: str
    result: Literal["positive", "negative", "ambiguous"]
    score: float | None = None
    qc_metrics: dict[str, Any] | None = None
    uploaded_by: str
    timestamp: datetime
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def qc_check(label: ExperimentLabel) -> tuple[bool, list[str]]:
    issues: list[str] = []
    metrics = label.qc_metrics or {}

    if label.assay_type == "MS":
        psm_count = metrics.get("psm_count")
        fdr = metrics.get("fdr")
        if psm_count is not None and psm_count < 3:
            issues.append("MS label rejected: psm_count below minimum threshold 3")
        if fdr is not None and fdr > 0.01:
            issues.append("MS label rejected: fdr exceeds threshold 0.01")

    return len(issues) == 0, issues


def ingest_labels(
    raw_labels: list[dict],
    uncertainty_threshold: float = 0.7,
    store: LearningStore | None = None,
    enforce_schema: bool = True,
) -> dict:
    store = store or LearningStore()

    schema_errors: list[dict] = []
    if enforce_schema:
        for i, raw in enumerate(raw_labels):
            errs = validate_against_schema(raw)
            if errs:
                schema_errors.append({"index": i, "label_id": raw.get("label_id", "?"), "errors": errs})

    parsed: list[ExperimentLabel] = [ExperimentLabel.model_validate(item) for item in raw_labels]

    accepted = 0
    flagged = 0
    high_uncertainty: list[str] = []

    for item in parsed:
        item.qc_metrics = item.qc_metrics or {}
        valid, issues = qc_check(item)
        if valid:
            accepted += 1
            item.qc_metrics["flagged"] = False
        else:
            flagged += 1
            item.qc_metrics["flagged"] = True
            item.qc_metrics["issues"] = issues
            store.append_audit_event(
                action="label_qc",
                status="flagged",
                details={"label_id": item.label_id, "issues": issues},
            )

        if item.uncertainty >= uncertainty_threshold:
            high_uncertainty.append(item.peptide_id)

    batch_id = store.log_label_ingestion(
        total_count=len(parsed),
        accepted_count=accepted,
        flagged_count=flagged,
        high_uncertainty_count=len(high_uncertainty),
    )

    if high_uncertainty:
        store.log_acquisition_batch(batch_id=batch_id, peptide_ids=high_uncertainty)

    return {
        "batch_id": batch_id,
        "total": len(parsed),
        "accepted": accepted,
        "flagged": flagged,
        "high_uncertainty_peptides": high_uncertainty,
        "schema_errors": schema_errors,
        "parsed_labels": parsed,
    }
