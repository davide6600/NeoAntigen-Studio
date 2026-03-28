# NeoAntigen-Studio Documentation Index

## Purpose

This index tracks the project documents that define architecture, governance, safety controls, operations, and learning workflows.

Use this file as the first checkpoint in future sessions to quickly locate authoritative guidance and keep documentation changes auditable.

## Core Governance and Architecture

- `AGENTS.md`: Stable execution guidance for coding agents, including periodic consolidation of recurring learnings.
- `ARCHITECTURE.md`: End-to-end platform architecture, RUO boundaries, active-learning design, and biosecurity controls.
- `ARCHITECTURE_IMPLEMENTATION_PLAN.md`: Planned implementation phases and delivery sequencing.
- `Architecture_Traceability_Matrix.md`: Requirement-to-implementation traceability.
- `README.md`: Public-facing repository entry point. Includes prominent Research-Only disclaimer, critical **System Requirements Notice** (Python 3.10-3.12 for MHCflurry), manual installation requirements for DTU binaries, and primary local execution commands.
- `CONTRIBUTING.md`: Open-source contributor guidelines, PR workflow, develop setup, and safety-critical review requirements.
- `CODE_OF_CONDUCT.md`: Contributor Covenant with additional biomedical open-source standards.
- `SECURITY.md`: Vulnerability disclosure process and biosecurity-specific security architecture.
- `CHANGELOG.md`: Version history and notable changes tracking.
- `LICENSE`: Apache 2.0 license file.

## Runbooks and Compliance

- `docs/runbooks/incident_response.md`: Mitigation steps for security, infra, or data integrity incidents.
- `docs/runbooks/canary_rollback.md`: Procedures for reverting MLflow model deployments safely.
- `docs/runbooks/export_approval_workflow.md`: The biosecurity human-in-the-loop approval and manifest sequence workflow.
- `docs/compliance/ruo_policy.md`: Platform-wide binding assertions restricting models and outputs to Research Use Only.
- `docs/compliance/approval_logs.md`: The persistence architecture and schema guarantees for immutable event logging.
- `docs/compliance/provenance_examples.md`: Expected metadata schemas linking generated artifacts to inputs, parameters, and tool versions.
- `docs/compliance/intervention_audit.md`: Manual intervention and audit logging policy for clinical research data modifications.

## Agent Operations and Safety

- `agent/README.md`: Agent runtime guide, safety rules, approval flow, QA/debugging mindset, startup behavior.
- `agent/manifest.json`: Agent roles, capabilities, startup indexing behavior, and safety policy flags.
- `agent/checklist.md`: Critical actions that require explicit human approval and designated approvers.
- `agent/proposals/proposal.md`: Proposal and approval token template for gated actions.
- `agent/report_bootstrap.md`: Bootstrap status report of scaffolded components and test instructions.
- `agent/report_phase1_foundation_delta_2026-03-15.md`: Latest implementation delta and validation evidence for the Phase 1 foundation slice.
- `agent/report_phase2_execution_learnings_2026-03-26.md`: Consolidated Phase 2 retrospective covering Nextflow integration, Sklearn mock fallbacks, and HMAC approval generation.
- `agent/report_phase3_execution_learnings_2026-03-15.md`: Consolidated Phase 3 retrospective covering MLflow pipeline logic, predictors execution, and test assertion pitfalls.
- `agent/report_phase4_execution_learnings_2026-03-15.md`: Consolidated Phase 4 retrospective covering mRNA design logic, Biosecurity safety gates, and Pydantic v2 typing insights.
- `agent/report_phase5_execution_learnings_2026-03-15.md`: Consolidated Phase 5 retrospective covering wet-lab and LIMS integration, PostgreSQL dict_row patterns, and active-learning retraining triggers.
- `agent/report_phase6_execution_learnings_2026-03-16.md`: Consolidated Phase 6 retrospective covering frontend Vite scaffolding, CSS design tokens, and observability.
- `agent/report_phase7_execution_learnings_2026-03-17.md`: Consolidated Phase 7 retrospective covering Production Validation and exhaustive Mock Dummy Elimination across API, Worker and Test spheres.
- `starting_prompt.md`: Standard startup briefing protocol for future sessions.

## Schema and Data Contracts

- `schemas/experiment_label.json`: Canonical schema for wet-lab experimental labels and QC fields.
- `migrations/postgresql/0001_core_schema.sql`: Initial relational schema baseline.
- `migrations/postgresql/0002_job_lifecycle_schema.sql`: Job and artifact lifecycle schema for API/worker persistence.
- `migrations/postgresql/README.md`: Migration usage and operational notes.


## CI, Build, and Test

- `.github/workflows/bootstrap-smoke.yml`: Main CI workflow for governance checks, unit tests, and Nextflow smoke logic.
- `agent/ci/ci.yml`: Agent CI template mirroring bootstrap checks.
- `pyproject.toml`: Python packaging, pinned dependencies, and pytest config.
- `Makefile`: Project orchestration for Docker services, migrations, and E2E testing.
- `docker-compose.yml`: Local runtime stack for API, worker, Redis, and PostgreSQL with pre-configured persistence.
- `containers/Dockerfile.api`: Docker image specification for the FastAPI backend.
- `containers/Dockerfile.worker`: Docker image specification for the Celery component with optional NetMHCpan support.
- `scripts/docker_start.sh`: Shell script to easily assemble and orchestrate the Phase 4 docker-compose stack.
- `scripts/install_netmhcpan.sh`: Helper script for manual host-level NetMHCpan integration.
- `scripts/setup_predictors.sh`: Local setup helper for enabling MHCflurry model downloads and a smoke prediction check.
- `workflows/neoantigen.nf`: HPC-oriented Nextflow DSL2 wrapper for HLA typing, Phase 2 prediction, and PDF report generation.
- `workflows/nextflow.config`: Profile entrypoint for standard, slurm, conda, docker, and test execution modes.
- `workflows/conf/base.config`: Default CPU, memory, and runtime settings for the HPC wrapper.
- `workflows/conf/slurm.config`: SLURM-specific executor and cluster option overrides for the HPC wrapper.
- `workflows/conf/conda.config`: Conda enablement for the HPC wrapper using the bundled environment file.
- `workflows/environment.yml`: Python 3.11 and Bioconda environment definition for HPC and MHCflurry compatibility.
- `workflows/run_test.sh`: Shell-based smoke test for the HPC wrapper when Nextflow is installed.
- `start_neoantigen_studio_light.bat`: Utility script for fast deployment of API without full stack capabilities.
- `start_neoantigen_studio_full.bat`: Full launch script relying on docker-compose for comprehensive ecosystem standup.
- `QA_tests/AI_QA_Tester_Credentials.md`: Credential setup instructions for running AI QA Tester locally and in CI.

## Runtime Components

- `services/api/main.py`: API entrypoint.
- `services/api/object_store.py`: Pluggable object store backends (local and MinIO/S3-compatible), including presigned download URL support for remote artifacts.
- `services/api/job_store.py`: Job lifecycle persistence abstraction with SQLite fallback and PostgreSQL backend support.
- `services/api/migrations.py`: Migration discovery and PostgreSQL apply runner.
- `services/api/main.py`: API entrypoint including Phase 2 entities endpoint for normalized PostgreSQL-backed reads with filtering, pagination, requester/project scope checks, and remote artifact/report download resolution.
- `services/worker/tasks.py`: Background task orchestration.
- `services/worker/pipeline_runtime.py`: Phase 2 minimal pipeline runtime with deterministic synthetic execution and optional Nextflow execution.
- `services/worker/phase2_predictors.py`: Shared Phase 2 scoring contract now delegating binding calls to the real predictor cascade while preserving ranking outputs.
- `services/worker/hla_typing.py`: HLA-I typing resolution layer with OptiType-first lookup, manifest fallback, and demo-only defaults.
- `services/worker/pvacseq_backend.py`: Optional pVACseq wrapper for academic-grade neoantigen scoring, with safe runtime fallback when unavailable.
- `services/worker/real_predictors.py`: Real MHC-I predictor cascade with MHCflurry, IEDB API fallback, and deterministic stub fallback.
- `services/worker/phase2_postgres_persistence.py`: Phase 2 normalized PostgreSQL persistence bridge for sequence-run lineage, variant, peptide candidate, prediction, and provenance tables.
- `services/worker/celery_app.py`: Celery worker registration and task binding.
- `services/frontend/src/components/jobs/StepDetailPanel.tsx`: UI component for pipeline step drill-down and manual intervention.
- `services/frontend/src/components/jobs/JobTable.tsx`: Enhanced job dashboard with pipeline timeline visualization.
- `scripts/run_pipeline_cli.py`: End-to-end CLI tool for job submission, automated polling, and comprehensive audit trail printing.
- `scripts/generate_approval_token.py`: Utility script for generating standalone HMAC SHA-256 tokens for gated biosecurity export approval steps.
- `scripts/test_full_approval_flow.py`: Automated E2E test script to spin up the API and verify HMAC token-based workflows.
- `agent/skills/`: Skill implementations (acquisition, label ingest, model retrain, mRNA design, sequence safety, orchestration, ml trainer).
- `agent/context/indexer.py`: Startup context indexing and retrieval foundation.
- `agent/learnings/store.py`: Learning and event persistence.


## 2026-03 Scientific Prediction Stack

| File | Descrizione | Stato | Python |
|------|-------------|-------|--------|
| `services/worker/real_predictors.py` | Cascata MHCflurry -> IEDB API -> stub per predizioni MHC-I reali | ⚠️ Richiede setup | 3.10–3.12 |
| `services/worker/pvacseq_backend.py` | Wrapper opzionale per pVACseq CLI integrabile come backend alternativo | ⚠️ Richiede setup | 3.10+ |
| `services/worker/stability_predictor.py` | Predizione di stabilita peptide-MHC con API reale e fallback controllato | ✅ Produzione | 3.10+ |
| `services/worker/tcr_recognition.py` | Predizione riconoscimento TCR con backend reali e fallback esplicito | ✅ Produzione | 3.10+ |
| `services/worker/cohort_analysis.py` | Analisi multi-paziente: aggregazione, shared peptides, heatmap, export CSV | ✅ Produzione | 3.10+ |
| `services/worker/phase2_predictors.py` | Ranking Phase 2 con binding, stabilita, TCR, `predictor_used` e `scores_are_partial` | ✅ Produzione | 3.10+ |
| `services/worker/hla_typing.py` | HLA typing a cascata OptiType -> HLA-HD -> stub con `HLATypingResult` | ⚠️ Richiede setup | 3.10+ |
| `benchmark/` | Benchmark TESLA, dataset locali di validazione, runner CLI e documentazione benchmark | 🔬 Research | 3.10+ |
| `benchmark/tesla_validated.csv` | Mini-cohort TESLA con controlli immunogenici e negativi per validazione reale via IEDB API | 🔬 Research | n/a |
| `benchmark/run_tesla_benchmark.py` | Runner standalone con cache, metriche ROC/PR e report JSON per il benchmark TESLA | ✅ Produzione | 3.10+ |
| `tests/test_benchmark.py` | Test del runner TESLA, della cache e dello schema del report con mock offline | ✅ Produzione | 3.10+ |
| `scripts/setup_predictors.sh` | Setup guidato dei predictor reali e note di compatibilita Python/MHCflurry | ⚠️ Richiede setup | n/a |
| `pyproject.toml` | Dipendenze scientifiche, marker pytest `slow`/`network`, cache e compatibilita runtime | ✅ Produzione | 3.10+ |
| `README.md` | Documentazione pubblica aggiornata con Prediction Backends, HLA Typing, Benchmark e HPC usage | ✅ Produzione | n/a |

## Pipeline Definitions

- `pipelines/nextflow/smoke_test/main.nf`: Bootstrap smoke workflow used for environment validation.
- `pipelines/nextflow/main.nf`: Phase 2 minimal workflow scaffold for preprocessing, variant annotation, peptide ranking, and feature export.

## Phase 2 Validation

- `tests/test_phase2_pipeline_runtime.py`: Deterministic runtime contract tests for synthetic Phase 2 execution.
- `tests/test_phase2_predictors.py`: Unit tests for the shared Phase 2 predictor contract with mocked real-predictor cascade outputs.
- `tests/test_hla_typing.py`: Unit tests for HLA allele validation, manifest/default resolution, and candidate allele propagation.
- `tests/test_pvacseq_backend.py`: Optional-backend contract tests for pVACseq availability detection, stub fallback, and synthetic VCF generation.
- `tests/test_real_predictors.py`: Contract tests for the real predictor cascade schema and deterministic stub fallback behavior.
- `tests/test_phase2_postgres_persistence.py`: Unit tests for normalized PostgreSQL persistence bridge behavior.
- `tests/test_phase2_worker_postgres_bridge.py`: Worker-level test validating Phase 2 execution integration with persistence bridge and artifact registration.
- `tests/test_phase2_entities_api.py`: API-level tests for normalized Phase 2 entities retrieval and database precondition checks.
- `tests/test_phase2_entities_audit.py`: Audit-path tests for rejected and allowed entities access decisions.
- `tests/integration/test_phase2_pipeline_execution.py`: API-level integration test for phase2_real execution and result/provenance contract.

## Phase 3 Validation

- `tests/test_model_pipeline_api.py`: Tests the `/models/retrain`, `/models/{id}/promote`, and `/models/{id}/rollback` MLflow API endpoints.

## Phase 4 Validation

- `tests/test_docker_config.py`: Tests that the `docker-compose.yml` and Dockerfile manifests are syntactically valid and contain expected configurations without needing a live Docker daemon.

## Session Update Protocol (Mandatory)

When a session modifies docs, learnings policy, governance flow, safety controls, CI behavior, schemas, or startup behavior:

1. Update this file in the same session.
2. Add any newly created documentation files to the relevant section.
3. Remove or rename stale entries when documents move.
4. Keep descriptions short and operational (what the file governs).
5. Include touched-file rationale in the session report for auditability.

## Last Updated

- Date: 2026-03-27
- Reason: Documented the HPC Nextflow wrapper and the TESLA validation benchmark assets added in this session.
