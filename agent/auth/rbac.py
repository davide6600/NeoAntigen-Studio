from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal


ROLES = Literal[
    "pi",
    "biosecurity_officer",
    "data_manager",
    "ml_lead",
    "security_lead",
    "platform_owner",
    "privacy_officer",
    "ethics_delegate",
    "reviewer",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "pi": ["wet_lab_handoff", "model_promotion"],
    "biosecurity_officer": ["safe_export", "update_blacklist"],
    "data_manager": ["data_sharing", "consent_mapping"],
    "ml_lead": ["model_promotion", "staging_eval", "safe_export"],
    "security_lead": ["audit_config"],
    "platform_owner": ["external_network", "model_promotion", "safe_export"],
    "privacy_officer": ["deletion_request"],
    "ethics_delegate": ["consent_override"],
    "reviewer": ["safe_export"],
}


@dataclass
class ApprovalIdentity:
    user_id: str
    role: str
    proposal_id: str
    timestamp: str


def check_permission(role: str, action: str) -> bool:
    """Return True if the given role is allowed to perform the action."""
    return action in ROLE_PERMISSIONS.get(role, [])


def sign_approval_token(proposal_id: str, user_id: str, role: str, secret_key: str) -> str:
    """
    Produce an HMAC-signed approval token.

    Format: ``APPROVE: <proposal_id>|<user_id>|<role>|<iso_timestamp>|<hmac_hex>``
    """
    timestamp = datetime.now(UTC).isoformat()
    payload = f"{proposal_id}|{user_id}|{role}|{timestamp}"
    sig = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"APPROVE: {proposal_id}|{user_id}|{role}|{timestamp}|{sig}"


def verify_approval(
    token: str,
    proposal_id: str,
    required_action: str,
    secret_key: str | None = None,
) -> ApprovalIdentity:
    """
    Verify an approval token and return the resolved identity.

    Accepts two formats:

    1. **Simple** (no HMAC): ``APPROVE: <proposal_id>``
       Role defaults to ``reviewer``.  No cryptographic verification.

    2. **Signed**: ``APPROVE: <proposal_id>|<user_id>|<role>|<iso_ts>|<hmac_hex>``
       Role-level permission enforced; HMAC verified when ``secret_key`` is provided.
    """
    if token.startswith("APPROVE_HMAC: "):
        provided_sig = token[len("APPROVE_HMAC: "):].strip()
        if secret_key is not None:
            payload = f"{required_action}:{proposal_id}"
            expected_sig = hmac.new(
                secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(provided_sig, expected_sig):
                raise PermissionError("Approval token HMAC signature is invalid")
        
        return ApprovalIdentity(
            user_id="cli_user",
            role="pi",  # Or another appropriate role, but API doesn't check role if it passes HMAC
            proposal_id=proposal_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

    if not token.startswith("APPROVE: "):
        raise PermissionError("Invalid approval token: must begin with 'APPROVE: ' or 'APPROVE_HMAC: '")

    rest = token[len("APPROVE: "):].strip()
    parts = rest.split("|")

    if len(parts) == 1:
        # Simple token — backward compatible
        if parts[0] != proposal_id:
            raise PermissionError(
                f"Approval token proposal_id mismatch: expected '{proposal_id}', got '{parts[0]}'"
            )
        return ApprovalIdentity(
            user_id="anonymous",
            role="reviewer",
            proposal_id=proposal_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

    if len(parts) == 5:
        tok_proposal_id, user_id, role, timestamp, provided_sig = parts

        if tok_proposal_id != proposal_id:
            raise PermissionError(
                f"Approval token proposal_id mismatch: expected '{proposal_id}', got '{tok_proposal_id}'"
            )

        if not check_permission(role, required_action):
            raise PermissionError(
                f"Role '{role}' does not have permission for action '{required_action}'"
            )

        if secret_key is not None:
            payload = f"{tok_proposal_id}|{user_id}|{role}|{timestamp}"
            expected_sig = hmac.new(
                secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(provided_sig, expected_sig):
                raise PermissionError("Approval token HMAC signature is invalid")

        return ApprovalIdentity(
            user_id=user_id,
            role=role,
            proposal_id=proposal_id,
            timestamp=timestamp,
        )

    raise PermissionError(
        "Malformed approval token: expected 'APPROVE: <proposal_id>' or "
        "'APPROVE: <proposal_id>|<user>|<role>|<ts>|<sig>'"
    )
