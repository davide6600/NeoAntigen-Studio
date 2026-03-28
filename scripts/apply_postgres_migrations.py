from __future__ import annotations

import argparse

from services.api.migrations import apply_postgres_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply NeoAntigen Studio PostgreSQL migrations")
    parser.add_argument("--database-url", dest="database_url", default=None, help="PostgreSQL URL")
    args = parser.parse_args()

    applied = apply_postgres_migrations(database_url=args.database_url)
    if applied:
        print("Applied migrations:")
        for name in applied:
            print(f"- {name}")
    else:
        print("No migrations found to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
