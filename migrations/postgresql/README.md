# PostgreSQL Migrations

This directory contains ordered SQL migrations for the production PostgreSQL data plane.

## Rules

- Files are executed lexicographically.
- Use idempotent DDL (`IF NOT EXISTS`, `IF EXISTS`) where possible.
- Keep RUO and audit/provenance requirements in scope for schema updates.
- Schema changes that alter safety-critical behavior require approver sign-off.

## Current baseline

- `0001_core_schema.sql`: core entities for patient/sample/run/variant/peptide/prediction/label/TCR and provenance.
- `0002_job_lifecycle_schema.sql`: job status, artifacts, and audit log tables for API/worker lifecycle persistence.
