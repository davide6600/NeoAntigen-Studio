from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.api.migrations import apply_postgres_migrations, list_postgres_migration_files


def test_list_postgres_migration_files_returns_sorted_sql_files(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (migrations_dir / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "README.md").write_text("ignore", encoding="utf-8")

    files = list_postgres_migration_files(migrations_dir)
    assert [item.name for item in files] == ["0001_first.sql", "0002_second.sql"]


def test_core_schema_contains_required_tables():
    schema_path = Path("migrations/postgresql/0001_core_schema.sql")
    assert schema_path.exists()
    sql = schema_path.read_text(encoding="utf-8").lower()

    required_tables = [
        "create table if not exists patient",
        "create table if not exists sample",
        "create table if not exists sequence_run",
        "create table if not exists variant",
        "create table if not exists peptide_candidate",
        "create table if not exists prediction_record",
        "create table if not exists experiment_label",
        "create table if not exists tcr_record",
        "create table if not exists provenance_record",
    ]
    for table_ddl in required_tables:
        assert table_ddl in sql


def test_job_lifecycle_schema_contains_required_tables():
    schema_path = Path("migrations/postgresql/0002_job_lifecycle_schema.sql")
    assert schema_path.exists()
    sql = schema_path.read_text(encoding="utf-8").lower()

    required_tables = [
        "create table if not exists jobs",
        "create table if not exists job_artifacts",
        "create table if not exists audit_log",
    ]
    for table_ddl in required_tables:
        assert table_ddl in sql


def test_apply_postgres_migrations_requires_database_url():
    with pytest.raises(ValueError, match="database_url is required"):
        apply_postgres_migrations(database_url=None)


def test_apply_postgres_migrations_rejects_non_postgres_url(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0001_test.sql").write_text("SELECT 1;", encoding="utf-8")

    with pytest.raises(ValueError, match="Only PostgreSQL URLs are supported"):
        apply_postgres_migrations(database_url="sqlite:///tmp.db", migrations_dir=migrations_dir)


def test_apply_postgres_migrations_returns_empty_when_no_files(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)

    applied = apply_postgres_migrations(
        database_url="postgresql://user:pass@localhost:5432/neoantigen",
        migrations_dir=migrations_dir,
    )
    assert applied == []


def test_apply_postgres_migrations_raises_if_psycopg_missing(tmp_path, monkeypatch):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0001_test.sql").write_text("SELECT 1;", encoding="utf-8")

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("psycopg missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(RuntimeError, match="psycopg is required"):
        apply_postgres_migrations(
            database_url="postgresql://user:pass@localhost:5432/neoantigen",
            migrations_dir=migrations_dir,
        )


def test_apply_postgres_migrations_executes_sorted_sql_files(tmp_path, monkeypatch):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (migrations_dir / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")

    executed_sql: list[str] = []
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.execute.side_effect = lambda sql, *args: executed_sql.append(sql.strip())

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = None
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = None

    fake_psycopg = MagicMock()
    fake_psycopg.connect.return_value = connection

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    applied = apply_postgres_migrations(
        database_url="postgresql://user:pass@localhost:5432/neoantigen",
        migrations_dir=migrations_dir,
    )

    assert applied == ["0001_first.sql", "0002_second.sql"]
    assert "SELECT 1;" in executed_sql
    assert "SELECT 2;" in executed_sql
    assert executed_sql.index("SELECT 1;") < executed_sql.index("SELECT 2;")
    fake_psycopg.connect.assert_called_once_with(
        "postgresql://user:pass@localhost:5432/neoantigen",
        autocommit=True,
    )


def test_apply_postgres_migrations_skips_previously_applied_files(tmp_path, monkeypatch):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")

    executed_sql: list[str] = []
    cursor = MagicMock()
    cursor.fetchall.return_value = [("0001_first.sql",)]
    cursor.execute.side_effect = lambda sql, *args: executed_sql.append(sql.strip())

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = None
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = None

    fake_psycopg = MagicMock()
    fake_psycopg.connect.return_value = connection

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    applied = apply_postgres_migrations(
        database_url="postgresql://user:pass@localhost:5432/neoantigen",
        migrations_dir=migrations_dir,
    )

    assert applied == ["0002_second.sql"]
    assert "SELECT 1;" not in executed_sql
    assert "SELECT 2;" in executed_sql
