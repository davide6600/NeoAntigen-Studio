"""Tests for RBAC role permissions and HMAC-signed approval tokens."""
from __future__ import annotations

import pytest

from agent.auth.rbac import (
    ROLE_PERMISSIONS,
    ApprovalIdentity,
    sign_approval_token,
    verify_approval,
)

_SECRET = "test-secret-key"


class TestRolePermissions:
    def test_biosecurity_officer_can_safe_export(self):
        assert "safe_export" in ROLE_PERMISSIONS["biosecurity_officer"]

    def test_reviewer_cannot_promote_model(self):
        assert "model_promotion" not in ROLE_PERMISSIONS.get("reviewer", [])

    def test_ml_lead_can_promote(self):
        assert "model_promotion" in ROLE_PERMISSIONS["ml_lead"]


class TestSimpleTokenVerify:
    def test_valid_simple_token_passes(self):
        token = "APPROVE: prop-001"
        identity = verify_approval(token, "prop-001", required_action="safe_export")
        assert identity.proposal_id == "prop-001"

    def test_wrong_proposal_id_raises(self):
        token = "APPROVE: prop-001"
        with pytest.raises(PermissionError):
            verify_approval(token, "prop-002", required_action="safe_export")

    def test_malformed_token_raises(self):
        with pytest.raises(PermissionError):
            verify_approval("NOTVALID", "prop-001", required_action="safe_export")


class TestSignedToken:
    def test_roundtrip_signed_token(self):
        token = sign_approval_token("prop-42", "alice", "biosecurity_officer", _SECRET)
        assert token.startswith("APPROVE: ")
        identity = verify_approval(
            token, "prop-42", required_action="safe_export", secret_key=_SECRET
        )
        assert identity.user_id == "alice"
        assert identity.role == "biosecurity_officer"

    def test_tampered_token_raises(self):
        token = sign_approval_token("prop-42", "alice", "biosecurity_officer", _SECRET)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(PermissionError):
            verify_approval(tampered, "prop-42", required_action="safe_export", secret_key=_SECRET)

    def test_wrong_role_for_action_raises(self):
        # 'reviewer' cannot do 'model_promotion'
        token = sign_approval_token("prop-99", "bob", "reviewer", _SECRET)
        with pytest.raises(PermissionError):
            verify_approval(token, "prop-99", required_action="model_promotion", secret_key=_SECRET)

    def test_signed_token_wrong_proposal_raises(self):
        token = sign_approval_token("prop-1", "alice", "biosecurity_officer", _SECRET)
        with pytest.raises(PermissionError):
            verify_approval(token, "prop-2", required_action="safe_export", secret_key=_SECRET)

    def test_wrong_secret_raises(self):
        token = sign_approval_token("prop-1", "alice", "biosecurity_officer", _SECRET)
        with pytest.raises(PermissionError):
            verify_approval(token, "prop-1", required_action="safe_export", secret_key="wrong-key")
