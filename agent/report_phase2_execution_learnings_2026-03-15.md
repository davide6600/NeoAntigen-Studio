# Phase 2 Execution Learnings Report (2026-03-15)

## Purpose
This report consolidates the implementation patterns, remaining gaps, and execution learnings gathered while completing Phase 2 of the architecture.

## Scope Reviewed
1. Phase 2 pipeline runtime and Nextflow workflow execution.
2. Artifact persistence across local storage, PostgreSQL, and object-store mirrors.
3. Results API access patterns for local and remote artifacts.
4. CI contract enforcement for synthetic and Nextflow-backed paths.

## Effective Patterns
1. Shared contract modules reduce divergence.
- Moving peptide ranking logic into a shared wrapper module allowed the runtime path and the Nextflow path to emit the same ranked-peptide and feature-table shapes.
- This reduced duplication and made Phase 2 completion testable at the artifact-contract level rather than by implementation detail.

2. Deterministic synthetic execution is useful when scoped tightly.
- Synthetic generation remained valuable for Phase 2 because it exercised orchestration, persistence, audit, and artifact flows without introducing toolchain instability.
- Determinism was preserved by deriving stable scores and sequences from job and metadata inputs instead of time or ambient randomness.

3. Storage abstractions need both write and retrieval contracts.
- Object-store support initially solved upload and mirroring, but Phase 2 was not operationally complete until retrieval for remote artifacts was also represented in the API.
- Adding presigned-download behavior completed the storage contract for non-local backends.

4. Container-based CI checks are the safest place to validate real workflow shape.
- A dedicated CI container lane for the real Nextflow workflow provided a reliable guard against regressions in pipeline wiring without depending on every local environment having Nextflow installed.

5. Documentation updates must happen in the same session as implementation.
- The implementation plan and docs index were most useful when updated immediately after each completed vertical slice.
- Delaying these updates would have made the actual repository state harder to reconstruct.

## Gaps Closed During Execution
1. Phase 2 output artifacts are now optionally mirrored to configured object-store backends with persisted reference artifacts.
2. Results and report retrieval now handle remote artifact locations via presigned URLs.
3. The real Nextflow Phase 2 workflow is now exercised in CI instead of relying only on smoke-only validation.
4. Peptide scoring is now isolated behind a shared Phase 2 predictor-wrapper contract rather than duplicated inline.

## Remaining Gaps After Phase 2 Closeout
1. The predictor-wrapper layer is currently contract-complete but still stub-backed.
- The wrapper contract is ready for tool-backed implementations, but external predictor integrations remain Phase 3 work.

2. Nextflow execution is contract-validated, not locally universal.
- CI now enforces the real workflow path, but local execution still depends on developer environment availability for Nextflow.

3. Artifact retrieval is operational for remote stores, but access governance is still minimal.
- Presigned URL generation exists, but richer policies such as scoped TTL selection, per-role retrieval rules, and explicit download audit enrichment remain future hardening work.

4. Feature fidelity is still intentionally limited.
- Phase 2 proves execution plumbing, provenance, and persistence.
- It does not yet claim production-grade biological scoring fidelity.

## Execution Learnings
1. The fastest safe way to close architecture phases is to stabilize interfaces first, then deepen implementations behind those interfaces.
2. Test contracts should assert artifact semantics, provenance, and accessibility, not only success status.
3. Local placeholder artifacts under `data/` are a recurring byproduct of job and API tests and should be cleaned before finalizing diffs.
4. Cross-platform tests should continue using `pathlib` and avoid shell/path assumptions, especially in object-store and artifact assertions.
5. Phase boundaries are clearer when execution plumbing, storage, and observability are treated as completion criteria distinct from model sophistication.

## Recommended Carry-Forward Into Phase 3
1. Preserve the shared predictor-wrapper contract and replace internals behind it rather than altering Phase 2 artifact schemas.
2. Treat scoring-model upgrades as fidelity improvements, not as reasons to reopen Phase 2 execution semantics.
3. Keep CI split between contract tests and environment-gated tool execution so failures remain attributable.
4. Extend audit detail for remote artifact access before broadening external-facing usage.

## Validation Reference
Primary final validation used for Phase 2 closeout:

```bash
pytest -q tests/test_phase2_predictors.py tests/test_phase2_pipeline_runtime.py tests/integration/test_phase2_pipeline_execution.py tests/test_phase2_postgres_persistence.py tests/test_phase2_worker_postgres_bridge.py tests/test_phase2_entities_api.py tests/test_phase2_entities_audit.py
```