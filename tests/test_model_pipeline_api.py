from fastapi.testclient import TestClient
from services.api.main import app
from agent.auth.rbac import sign_approval_token
import os

client = TestClient(app)

def test_retrain_model_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "test_learnings.db"))
    
    response = client.post(
        "/models/retrain",
        json={
            "training_data_id": "dataset-123",
            "base_model_version": "seq2neo-v1"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "staged"
    assert data["approval_required"] is True
    assert data["model_version"].startswith("seq2neo-v1-staging-")
    
    # Check if the proposal is in pending approvals
    approvals_resp = client.get("/approvals")
    assert approvals_resp.status_code == 200
    pending = approvals_resp.json()["pending_approvals"]
    
    assert any(p["proposal_id"] == data["model_version"] for p in pending)


def test_promote_model_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "test_learnings.db"))
    monkeypatch.setenv("NEOANTIGEN_APPROVAL_SECRET", "test-secret")
    
    # First retrain to stage it
    retrain_resp = client.post(
        "/models/retrain",
        json={"training_data_id": "dataset-123", "base_model_version": "seq2neo-v1"}
    )
    model_version = retrain_resp.json()["model_version"]
    
    # Try promoting without correct token
    bad_promote = client.post(
        f"/models/{model_version}/promote",
        json={"approved_by": "test-user", "token": "APPROVE: bad-token"}
    )
    assert bad_promote.status_code == 403
    
    # Try promoting with correct token but wrong role (reviewer) - only ml_lead, pi, platform_owner are allowed
    bad_role_token = sign_approval_token(model_version, "test-user", "reviewer", "test-secret")
    bad_role_promote = client.post(
        f"/models/{model_version}/promote",
        json={"approved_by": "test-user", "token": bad_role_token}
    )
    assert bad_role_promote.status_code == 403
    
    # Promote with correct token and role
    good_token = sign_approval_token(model_version, "test-user", "ml_lead", "test-secret")
    promote_resp = client.post(
        f"/models/{model_version}/promote",
        json={"approved_by": "test-user", "token": good_token}
    )
    
    assert promote_resp.status_code == 200
    data = promote_resp.json()
    assert data["status"] == "promoted_to_production"
    assert data["canary_enabled"] is True


def test_rollback_model_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "test_learnings.db"))
    
    response = client.post(
        "/models/seq2neo-v1-staging-12345/rollback",
        json={"approved_by": "test-user", "reason": "model drifted in canary"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rolled_back"
    assert data["reason"] == "model drifted in canary"
