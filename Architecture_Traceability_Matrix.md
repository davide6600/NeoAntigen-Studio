# Architecture Traceability Matrix

This matrix maps architecture requirements to implementation modules, tests, and ownership.

| Requirement ID | Requirement | Module(s) | Test Coverage | Owner |
| --- | --- | --- | --- | --- |
| SAF-001 | RUO banner and policy always visible in API | services/api/main.py | tests/test_api.py | Platform Owner |
| SAF-002 | Sequence export requires explicit human approval token | agent/skills/mrna_designer.py, agent/auth/rbac.py | tests/test_mrna_designer.py, tests/test_rbac.py | Biosecurity Officer |
| SAF-003 | No autonomous wet-lab actions | agent/checklist.md, agent/README.md | Manual governance review | Principal Investigator |
| SAF-004 | Sensitive actions proposal-gated and audit logged | agent/proposals/proposal.md, agent/learnings/store.py | tests/test_startup_context.py | Security Lead |
| GOV-001 | Approval gate roles for critical operations | agent/checklist.md, agent/auth/rbac.py | tests/test_rbac.py | Security Lead |
| LAB-001 | Experiment labels must validate against schema + QC | schemas/experiment_label.json, agent/skills/label_ingest.py | tests/test_label_ingest.py | Data Governance Lead |
| API-001 | Health and context startup endpoints | services/api/main.py, agent/context/indexer.py | tests/test_api.py, tests/test_startup_context.py | Platform Owner |
| API-002 | Job lifecycle endpoints (submit/status/results/report) | services/api/main.py, services/worker/tasks.py, agent/learnings/store.py | tests/test_jobs_api.py | Platform Owner |
| API-003 | Label ingestion API endpoint | services/api/main.py, agent/skills/label_ingest.py | tests/test_jobs_api.py, tests/test_label_ingest.py | Data Manager |
| DATA-001 | Job state persisted with status transitions and audit events | agent/learnings/store.py | tests/test_jobs_api.py | Platform Owner |
| DATA-002 | Input files stored with checksum metadata | services/api/object_store.py, agent/learnings/store.py | tests/test_jobs_api.py | Platform Owner |
| PIPE-001 | Nextflow smoke orchestration path exists | pipelines/nextflow/smoke_test/main.nf, agent/skills/pipeline_orchestrator.py | tests/test_pipeline_orchestrator.py | MLOps Engineer |
| MLOPS-001 | Retrain recommendation and staging report flow | agent/skills/ml_trainer.py, agent/learnings/store.py | tests/test_ml_trainer.py, tests/integration/test_full_pipeline.py | ML Lead |
| PRIV-001 | Consent and deletion workflow persistence | agent/privacy/retention.py, agent/learnings/store.py | tests/test_retention.py | Privacy Officer |
| CI-001 | Unit and Nextflow smoke checks in CI | .github/workflows/bootstrap-smoke.yml | CI execution evidence | Platform Owner |

## Notes

- Current implementation covers Phases 1-6, including production integrations with PostgreSQL, Redis, MinIO, and a React frontend. The backend observability stack utilizes structlog and prometheus metrics.
- The platform enforces Research Use Only (RUO) and requires explicit human-in-the-loop approvals for biosecurity sequence exports.
- Any update to safety-critical requirements must include updated tests, a detailed phase completion report, and reviewer sign-off.
