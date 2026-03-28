from pathlib import Path

from agent.context.indexer import ContextIndexer
from agent.learnings.store import LearningStore


def test_load_context_includes_pending_approvals(tmp_path: Path) -> None:
    ctx_db = tmp_path / "context.db"
    learn_db = tmp_path / "learnings.db"

    store = LearningStore(db_path=str(learn_db))
    store.add_pending_approval("proposal-abc", "safe_export", {"target": "sequence.fasta"})

    # Ensure default db path points to our temp db for this test invocation.
    Path("agent/learnings").mkdir(parents=True, exist_ok=True)
    target_default = Path("agent/learnings/learnings.db")
    target_default.write_bytes(learn_db.read_bytes())

    indexer = ContextIndexer(db_path=str(ctx_db))
    summary = indexer.load_context()
    assert "pending_approvals" in summary
    assert any(item["proposal_id"] == "proposal-abc" for item in summary["pending_approvals"])
