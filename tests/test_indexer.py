from pathlib import Path

from agent.context.indexer import ContextIndexer


def test_index_file_inserts_chunks(tmp_path: Path) -> None:
    db = tmp_path / "ctx.db"
    indexer = ContextIndexer(db_path=str(db))

    doc = tmp_path / "doc.md"
    doc.write_text("hello world " * 100, encoding="utf-8")

    inserted = indexer.index_file(doc)
    assert inserted > 0
