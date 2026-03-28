# Phase 3 Execution Learnings (2026-03-15)

## Objective
Implement ML Scoring (Seq2Neo, MHC ensembles), active learning acquisition scoring, and model retraining/promotion pipelines for Phase 3.

## What went well
1. **Dynamic JSONB features:** Integrating acquisition and uncertainty scores required no PostgreSQL schema migrations because the `prediction_record.feature_snapshot` JSONB column natively absorbed the new fields.
2. **Modular Predictors:** Isolating predictors behind a consistent wrapper (`score_phase2_candidates` -> `score_phase3_candidates`) meant that `pipeline_runtime` only needed a mode configuration switch (`NEOANTIGEN_PHASE3_PREDICTOR_MODE`) without significantly altering the orchestrator logic.
3. **Reusing Phase 1 Approvals:** The `model_promotion` gate cleanly re-used the HMAC-signed `ApprovalIdentity` flow designed for object deletion, verifying that the RBAC enforcement pattern is stable and extensible.

## Pitfalls & Fixes
1. **Test Assertion Brittleness:** A heavy reliance on hardcoded pipeline version strings (`phase2-v0.2`) and stub names (`_stub_score`) across integration and unit tests meant that the transition to `phase3-v0.1` and `seq2neo` scores caused cascading test failures that required batch updating across `tests/integration/` and `tests/`. **Fix:** Updated the assertions; future tests should prefer dynamic prefix checking or test-specific fixtures rather than hardcoding global version strings deep in test files.
2. **Missing PYTHONPATH:** Running raw `pytest` without `$env:PYTHONPATH="."` led to 27 collection errors due to the root structure. **Fix:** Ensure CI/local validation always explicitly sets the python path.

## Repository Changes
- Created `services/worker/phase3_predictors.py` with `Seq2Neo` integration.
- Updated `services/worker/pipeline_runtime.py` to route Phase 3 jobs.
- Added `/models/retrain`, `/models/{id}/promote`, and `/models/{id}/rollback` endpoints to `services/api/main.py`.
- Added test suite `tests/test_model_pipeline_api.py`.
