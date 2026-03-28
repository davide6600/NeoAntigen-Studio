"""Tests for the FastAPI REST surface (services/api/main.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_status_ok(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_contains_ruo_flag(self):
        data = client.get("/health").json()
        assert "ruo" in data
        assert data["ruo"] is True


class TestContextEndpoint:
    def test_context_returns_200(self):
        resp = client.get("/context")
        assert resp.status_code == 200

    def test_context_returns_dict(self):
        data = client.get("/context").json()
        assert isinstance(data, dict)


class TestApprovalsEndpoint:
    def test_approvals_returns_200(self):
        resp = client.get("/approvals")
        assert resp.status_code == 200

    def test_approvals_returns_list(self):
        data = client.get("/approvals").json()
        assert isinstance(data.get("pending_approvals"), list)

    def test_approve_unknown_id_returns_404(self):
        resp = client.post(
            "/approvals/nonexistent-id/approve",
            json={"approved_by": "tester", "token": "APPROVE: nonexistent-id"},
        )
        assert resp.status_code == 404


class TestModelSummaryEndpoint:
    def test_model_summary_returns_200(self):
        resp = client.get("/model-summary")
        assert resp.status_code == 200

    def test_model_summary_returns_dict(self):
        data = client.get("/model-summary").json()
        assert isinstance(data, dict)
