from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

from agent.learnings.store import LearningStore
from agent.skills.skill_registry import SkillRegistry


class ContextIndexer:
    def __init__(self, db_path: str = "agent/context/context_index.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _embed_text(text: str, dims: int = 12) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(digest[i] / 255.0, 6) for i in range(dims)]

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 800) -> list[str]:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    def index_file(self, file_path: Path) -> int:
        if not file_path.exists() or not file_path.is_file():
            return 0

        text = file_path.read_text(encoding="utf-8")
        chunks = self._chunk_text(text)

        with self._connect() as conn:
            inserted = 0
            for chunk in chunks:
                conn.execute(
                    "INSERT INTO context_chunks (source, chunk_text, embedding, created_at) VALUES (?, ?, ?, datetime('now'))",
                    (str(file_path), chunk, json.dumps(self._embed_text(chunk))),
                )
                inserted += 1
        return inserted

    def index_commit_messages(self, limit: int = 20) -> int:
        try:
            output = subprocess.check_output(
                ["git", "log", f"--max-count={limit}", "--pretty=%h %s"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 0

        if not output.strip():
            return 0

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO context_chunks (source, chunk_text, embedding, created_at) VALUES (?, ?, ?, datetime('now'))",
                ("git:commits", output.strip(), json.dumps(self._embed_text(output.strip()))),
            )
        return 1

    def load_context(self) -> dict:
        repo_root = Path(".")

        docs = [repo_root / "ARCHITECTURE.md", repo_root / "README.md"]
        docs_dir = repo_root / "docs"
        if docs_dir.exists():
            docs.extend(sorted(docs_dir.glob("*.md")))

        indexed_count = 0
        for doc in docs:
            indexed_count += self.index_file(doc)
        indexed_count += self.index_commit_messages(limit=20)

        registry = SkillRegistry()
        store = LearningStore()

        return {
            "indexed_chunks": indexed_count,
            "repository_version": self._repository_version(),
            "top_skills": [s.name for s in registry.list_skills()[:5]],
            "last_learnings": store.get_last_learnings(limit=5),
            "pending_approvals": store.list_pending_approvals(limit=20),
            "next_actions": [f"APPROVE: {p['proposal_id']}" for p in store.list_pending_approvals(limit=5)],
        }

    @staticmethod
    def _repository_version() -> str:
        try:
            version = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unversioned"
        return version or "unversioned"
