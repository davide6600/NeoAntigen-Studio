from pathlib import Path

import pytest

from agent.learnings.store import LearningStore
from agent.skills.mrna_designer import safe_export


def test_safe_export_requires_approval_token(tmp_path: Path) -> None:
    db = tmp_path / "learnings.db"
    store = LearningStore(db_path=str(db))

    with pytest.raises(PermissionError):
        safe_export(
            sequence="AUGGCU",
            destination_path=str(tmp_path / "out.fasta"),
            proposal_id="proposal-1",
            approval_token="DENY",
            approved_by="reviewer",
            store=store,
        )


def test_safe_export_writes_sequence_when_approved(tmp_path: Path) -> None:
    db = tmp_path / "learnings.db"
    store = LearningStore(db_path=str(db))
    out = tmp_path / "sequence.fasta"

    result = safe_export(
        sequence="AUGGCU",
        destination_path=str(out),
        proposal_id="proposal-2",
        approval_token="APPROVE: proposal-2",
        approved_by="biosecurity_officer",
        store=store,
    )

    assert out.exists()
    assert result["proposal_id"] == "proposal-2"
