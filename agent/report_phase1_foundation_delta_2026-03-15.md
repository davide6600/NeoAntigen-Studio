# Phase 1 Foundation Delta Report (2026-03-15)

## Scope
This report captures the latest implementation delta for the Phase 1 Data + API + Queue foundation track.

## Implemented Delta
1. Added PostgreSQL core schema baseline migration in migrations/postgresql/0001_core_schema.sql covering:
- patient
- sample
- sequence_run
- variant
- peptide_candidate
- prediction_record
- experiment_label
- tcr_record
- provenance_record

2. Added migration discovery and apply runner in services/api/migrations.py.
3. Added operational migration script in scripts/apply_postgres_migrations.py.
4. Added PostgreSQL job lifecycle migration in migrations/postgresql/0002_job_lifecycle_schema.sql for jobs, artifacts, and audit events.
5. Added migration integrity tests in tests/test_postgres_migrations.py for:
- ordered migration file discovery
- required schema tables present in baseline migration
- required lifecycle tables present in job migration
- invalid URL rejection
- missing URL rejection
- empty migration directory behavior
- missing psycopg dependency handling
- deterministic sorted apply execution order

6. Added object store backend selection and MinIO implementation in services/api/object_store.py and wired API usage through services/api/main.py.
7. Added object store backend tests in tests/test_object_store.py, including cross-platform path-safe assertions.
8. Added local runtime stack artifacts:
- docker-compose.yml
- containers/Dockerfiles/runtime.Dockerfile
- services/worker/celery_app.py
9. Added backend-agnostic job lifecycle persistence in services/api/job_store.py with:
- SQLite-backed adapter for existing bootstrap flow
- PostgreSQL-backed adapter selected via NEOANTIGEN_DATABASE_URL
- API and worker execution paths wired to the shared job store abstraction
10. Added job store backend-selection tests in tests/test_job_store.py.

## Validation Evidence
1. Focused validation passed:
- pytest -q tests/test_object_store.py tests/test_postgres_migrations.py

2. Full repository test suite passed:
- pytest -q

## RUO and Governance Alignment
1. No autonomous wet-lab pathways were introduced.
2. Export approval gating and safety controls remain in existing guarded modules.
3. Migration flow remains deterministic and auditable through ordered SQL files and explicit apply script.

## Remaining Priority Work
1. Wire production PostgreSQL-backed job metadata persistence through API job lifecycle paths.
2. Expand contract tests for required Phase 1 API endpoints under PostgreSQL + object store integration.
3. Add queue integration tests for API enqueue to Celery worker execution path in local stack.
