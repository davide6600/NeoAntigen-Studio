from __future__ import annotations

from agent.learnings.store import LearningStore


def check_consent(patient_id: str, use_case: str, store: LearningStore | None = None) -> bool:
    """Return True only if the patient has active consent for the specified use case."""
    store = store or LearningStore()
    record = store.get_consent_record(patient_id)
    if record is None:
        return False
    if record["consent_status"] != "consented":
        return False
    return use_case in record.get("allowed_uses", [])


def schedule_deletion(
    patient_id: str,
    reason: str,
    requester_id: str,
    store: LearningStore | None = None,
) -> str:
    """
    Create a pending deletion request. Does NOT delete any data immediately.

    Returns the request_id for subsequent approval and execution.
    """
    store = store or LearningStore()
    return store.create_deletion_request(
        patient_id=patient_id,
        reason=reason,
        requester_id=requester_id,
    )


def execute_deletion(
    request_id: str,
    approved_by: str,
    store: LearningStore | None = None,
    object_store=None,
    object_paths: list[str] | None = None,
) -> dict:
    """
    Execute an approved deletion request.

    Soft-deletes the consent record and, when provided, deletes approved object
    store artifacts and records them in the audit log.

    Requires a prior call to ``schedule_deletion`` and explicit human approval.
    """
    store = store or LearningStore()
    request = store.get_deletion_request(request_id)
    if request is None:
        raise ValueError(f"Deletion request '{request_id}' not found")

    patient_id = request["patient_id"]
    deleted_object_paths: list[str] = []
    for path in object_paths or []:
        if object_store is None:
            raise ValueError("object_store is required when object_paths are provided")
        deleted = object_store.delete_path(path)
        if not deleted:
            raise ValueError(f"Object path '{path}' was not found or could not be deleted")
        deleted_object_paths.append(path)

    store.soft_delete_consent(patient_id)
    store.mark_deletion_request_executed(request_id, executed_by=approved_by)
    store.append_audit_event(
        action="data_deletion",
        status="executed",
        details={
            "request_id": request_id,
            "patient_id": patient_id,
            "approved_by": approved_by,
            "deleted_object_paths": deleted_object_paths,
            "note": "Consent record soft-deleted and approved object-store deletions executed.",
        },
    )
    return {
        "request_id": request_id,
        "patient_id": patient_id,
        "status": "executed",
        "approved_by": approved_by,
        "deleted_object_paths": deleted_object_paths,
    }
