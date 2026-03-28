from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script_module():
    script_path = Path("scripts/apply_postgres_migrations.py")
    spec = importlib.util.spec_from_file_location("apply_postgres_migrations_script", script_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_prints_no_migrations_message(monkeypatch, capsys):
    module = _load_script_module()

    captured: dict[str, str | None] = {"database_url": "not-set"}

    def fake_apply_postgres_migrations(*, database_url=None):
        captured["database_url"] = database_url
        return []

    monkeypatch.setattr(module, "apply_postgres_migrations", fake_apply_postgres_migrations)
    monkeypatch.setattr(sys, "argv", ["apply_postgres_migrations.py"])

    exit_code = module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert captured["database_url"] is None
    assert output.strip() == "No migrations found to apply."


def test_script_prints_applied_migrations(monkeypatch, capsys):
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "apply_postgres_migrations",
        lambda *, database_url=None: ["0001_core_schema.sql", "0002_job_lifecycle_schema.sql"],
    )
    monkeypatch.setattr(sys, "argv", ["apply_postgres_migrations.py"])

    exit_code = module.main()
    output_lines = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert output_lines == [
        "Applied migrations:",
        "- 0001_core_schema.sql",
        "- 0002_job_lifecycle_schema.sql",
    ]


def test_script_forwards_database_url_argument(monkeypatch, capsys):
    module = _load_script_module()

    captured: dict[str, str | None] = {"database_url": None}

    def fake_apply_postgres_migrations(*, database_url=None):
        captured["database_url"] = database_url
        return []

    monkeypatch.setattr(module, "apply_postgres_migrations", fake_apply_postgres_migrations)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "apply_postgres_migrations.py",
            "--database-url",
            "postgresql://user:pass@localhost:5432/neoantigen",
        ],
    )

    exit_code = module.main()
    _ = capsys.readouterr()

    assert exit_code == 0
    assert captured["database_url"] == "postgresql://user:pass@localhost:5432/neoantigen"