from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from agent.auth.rbac import sign_approval_token
from agent.learnings.store import LearningStore
from services.api.main import app


def test_create_deletion_request_returns_pending(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    client = TestClient(app)

    resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-001",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"].startswith("del-")
    assert data["status"] == "pending"
    assert data["approval_required"] is True
    assert data["ruo"] is True


def test_get_deletion_request_status_returns_record(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    client = TestClient(app)
    store = LearningStore(db_path=str(db_path))

    request_id = store.create_deletion_request("patient-002", "gdpr", "tester")

    resp = client.get(f"/deletions/{request_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == request_id
    assert data["patient_id"] == "patient-002"
    assert data["status"] == "pending"
    assert data["ruo"] is True


def test_execute_deletion_request_removes_object_and_marks_executed(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "local")
    monkeypatch.setenv("NEOANTIGEN_LOCAL_OBJECT_ROOT", str(tmp_path / "objects"))
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-003",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]

    stored_path = tmp_path / "objects" / "job-1" / "tumor.fastq"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("ABCD", encoding="utf-8")

    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "privacy-officer",
            "token": f"APPROVE: {request_id}",
            "object_paths": [str(stored_path)],
        },
    )

    assert execute_resp.status_code == 200
    data = execute_resp.json()
    assert data["request_id"] == request_id
    assert data["status"] == "executed"
    assert data["deleted_object_paths"] == [str(stored_path)]
    assert data["ruo"] is True
    assert not stored_path.exists()

    with sqlite3.connect(db_path) as conn:
        request_row = conn.execute(
            "SELECT status FROM deletion_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        approval_row = conn.execute(
            "SELECT status FROM pending_approvals WHERE proposal_id = ?",
            (request_id,),
        ).fetchone()
        audit_row = conn.execute(
            """
            SELECT details_json
            FROM audit_log
            WHERE action = 'data_deletion'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert request_row is not None
    assert request_row[0] == "executed"
    assert approval_row is not None
    assert approval_row[0] == "approved"
    assert audit_row is not None
    assert json.loads(audit_row[0])["deleted_object_paths"] == [str(stored_path)]


def test_execute_deletion_request_writes_human_approval_audit(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret-key")
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-007",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]
    token = sign_approval_token(request_id, "alice", "privacy_officer", "test-secret-key")

    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "alice",
            "token": token,
            "object_paths": [],
        },
    )

    assert execute_resp.status_code == 200

    with sqlite3.connect(db_path) as conn:
        approval_audit_row = conn.execute(
            """
            SELECT details_json
            FROM audit_log
            WHERE action = 'human_approval'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert approval_audit_row is not None
    details = json.loads(approval_audit_row[0])
    assert details["proposal_id"] == request_id
    assert details["approved_by"] == "alice"
    assert details["approval_role"] == "privacy_officer"
    assert details["approval_user_id"] == "alice"


def test_execute_deletion_request_rejects_invalid_token(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-004",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]

    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "privacy-officer",
            "token": "DENY",
            "object_paths": [],
        },
    )

    assert execute_resp.status_code == 403
    assert "Invalid approval token" in execute_resp.json()["detail"]


def test_execute_deletion_request_accepts_signed_privacy_officer_token(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret-key")
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-005",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]
    token = sign_approval_token(request_id, "alice", "privacy_officer", "test-secret-key")

    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "alice",
            "token": token,
            "object_paths": [],
        },
    )

    assert execute_resp.status_code == 200
    assert execute_resp.json()["status"] == "executed"


def test_execute_deletion_request_rejects_signed_wrong_role(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret-key")
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-006",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]
    token = sign_approval_token(request_id, "bob", "reviewer", "test-secret-key")

    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "bob",
            "token": token,
            "object_paths": [],
        },
    )

    assert execute_resp.status_code == 403
    assert "does not have permission" in execute_resp.json()["detail"]


def test_execute_deletion_request_rejects_replay_and_audits_rejection(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret-key")
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-008",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]
    token = sign_approval_token(request_id, "alice", "privacy_officer", "test-secret-key")

    first_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "alice",
            "token": token,
            "object_paths": [],
        },
    )
    assert first_resp.status_code == 200

    replay_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "alice",
            "token": token,
            "object_paths": [],
        },
    )

    assert replay_resp.status_code == 400
    assert "is not pending" in replay_resp.json()["detail"]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT details_json
            FROM audit_log
            WHERE action = 'human_approval' AND status = 'rejected'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert row is not None
    details = json.loads(row[0])
    assert details["proposal_id"] == request_id
    assert details["approved_by"] == "alice"
    assert details["reason"] == "request_not_pending"
    assert details["current_status"] == "executed"


def test_execute_deletion_request_rejects_invalid_object_path_and_audits_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "deletions.db"
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "local")
    monkeypatch.setenv("NEOANTIGEN_LOCAL_OBJECT_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret-key")
    client = TestClient(app)

    create_resp = client.post(
        "/deletions",
        json={
            "patient_id": "patient-009",
            "reason": "gdpr",
            "requester_id": "tester",
        },
    )
    request_id = create_resp.json()["request_id"]
    token = sign_approval_token(request_id, "alice", "privacy_officer", "test-secret-key")

    missing_path = tmp_path / "objects" / "missing.fastq"
    execute_resp = client.post(
        f"/deletions/{request_id}/execute",
        json={
            "approved_by": "alice",
            "token": token,
            "object_paths": [str(missing_path)],
        },
    )

    assert execute_resp.status_code == 400
    assert "was not found or could not be deleted" in execute_resp.json()["detail"]

    with sqlite3.connect(db_path) as conn:
        request_row = conn.execute(
            "SELECT status FROM deletion_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        approval_row = conn.execute(
            "SELECT status FROM pending_approvals WHERE proposal_id = ?",
            (request_id,),
        ).fetchone()
        audit_row = conn.execute(
            """
            SELECT details_json
            FROM audit_log
            WHERE action = 'human_approval' AND status = 'rejected'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert request_row is not None
    assert request_row[0] == "pending"
    assert approval_row is not None
    assert approval_row[0] == "pending"
    assert audit_row is not None
    details = json.loads(audit_row[0])
    assert details["proposal_id"] == request_id
    assert details["approved_by"] == "alice"
    assert details["approval_role"] == "privacy_officer"
    assert details["approval_user_id"] == "alice"
    assert details["reason"] == "execution_error"
    assert details["current_status"] == "pending"
