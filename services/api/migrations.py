from __future__ import annotations

import os
from pathlib import Path


_MIGRATIONS_DIR = Path("migrations/postgresql")


def _ensure_schema_migrations_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _list_applied_migrations(cur) -> set[str]:
    cur.execute("SELECT name FROM schema_migrations")
    rows = cur.fetchall()
    if not isinstance(rows, (list, tuple)):
        return set()
    return {str(row[0]) for row in rows if row and row[0] is not None}


def list_postgres_migration_files(migrations_dir: Path = _MIGRATIONS_DIR) -> list[Path]:
    if not migrations_dir.exists():
        return []
    return sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())


def apply_postgres_migrations(database_url: str | None = None, migrations_dir: Path = _MIGRATIONS_DIR) -> list[str]:
    """Apply SQL migrations to a PostgreSQL database.

    This function lazily imports psycopg so unit tests and bootstrap mode do not
    require PostgreSQL client libraries unless migrations are actually executed.
    """
    db_url = database_url or os.getenv("NEOANTIGEN_DATABASE_URL")
    if not db_url:
        raise ValueError("database_url is required (or set NEOANTIGEN_DATABASE_URL)")

    if not db_url.startswith("postgresql://") and not db_url.startswith("postgres://"):
        raise ValueError("Only PostgreSQL URLs are supported for apply_postgres_migrations")

    files = list_postgres_migration_files(migrations_dir)
    if not files:
        return []

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required to apply PostgreSQL migrations. Install with: pip install psycopg[binary]"
        ) from exc

    applied: list[str] = []
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            _ensure_schema_migrations_table(cur)
            applied_already = _list_applied_migrations(cur)

            for file_path in files:
                if file_path.name in applied_already:
                    continue

                sql = file_path.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)",
                    (file_path.name,),
                )
                applied.append(file_path.name)

    return applied
