# Phase 5 Execution Learnings

## Context
Phase 5 focused on implementing Wet-Lab/LIMS adapters and the Label Lifecycle. This included parsing LIMS manifests, robustly ingesting and QC-checking experimental labels, and persisting them properly into PostgreSQL. The final step was to link accepted human-reviewed labels to ML retraining triggers.

## Key Learnings & Emerging Patterns

1. **Dictionary Mutation During Iteration (PostgreSQL `dict_row`)**
   - **Gap:** When pulling rows from `psycopg` using `dict_row` factories, the resulting objects are dictionaries that get mutated in-place if standard keys are manipulated directly (e.g., date formatting). This causes typing linter errors (`Item assignment is not supported on dict[@_, @_]`). 
   - **Pattern:** Explicitly wrap `dict_row` objects in a new dictionary (`d = dict(r)`) before mutating keys like timestamps. This satisfies strict runtime analyzers and prevents mutable state leakage on the database cursor's row yields.

2. **UUID Slicing and Static Analyzer Limitations**
   - **Gap:** Expressions like `str(uuid.uuid4())[:8]` or `uuid.uuid4().hex[:8]` cause type-checker failures (`Cannot index into str` or `Argument slice[int, int, int] is not assignable to parameter...`) in advanced static analyzers like Pyre because it struggles to resolve `str.__getitem__` overloads for generated UUID string conversions.
   - **Pattern:** Avoid slicing generated UUID strings if Pyre complains. Instead, leverage string splitting (e.g., `str(uuid.uuid4()).split('-')[0]`) to get the first 8 characters, which resolves cleanly in all static type checkers without ambiguous slice overloads.

3. **Pydantic Validation Integrity**
   - **Gap:** When updating Pydantic models (like `ExperimentLabel`), accidentally removing fields triggers severe downstream validation errors if `extra='forbid'` is set.
   - **Pattern:** Ensure fields expected by incoming JSON objects are present (e.g., `score` and `uploaded_by`) even if they are optional or generated upstream.

4. **Database Row Nullability and Typing (`row[0]`)**
   - **Gap:** Unpacking `row[0] or {}` and mutating it directly throws static analysis errors (`Item assignment is not supported on dict[@_, @_] | Unknown`) because the dictionary type isn't fully inferred and the origin might be `None`.
   - **Pattern:** Resolve the null literal explicitly and copy into a strongly typed dictionary:
     `raw_flags = row[0] if row[0] is not None else {}`
     `qc_flags: dict[str, Any] = dict(raw_flags)` 
     This guarantees the static analyzer knows the object is safely mutable.

4. **Integration of ML Retraining Triggers**
   - **Gap:** Coupling label ingestion directly to ML model APIs requires careful construction of objects to not bypass the metadata expected by tools like MLflow staging checks.
   - **Pattern:** Invoke the full model pipeline staging wrapper (`stage_retrain`, `build_explainability_artifact`, `generate_staging_report`) from the ingestion component instead of isolating ML metrics logic to the `/models` endpoint. This guarantees consistency across MLflow staging records and proper human-approval staging hooks.

## Conclusion 
Phase 5 completes the active-learning loop. Manual human wet-lab uploads are correctly intercepted, scanned for anomalies, logged, and trigger a proposal for model retraining upon valid label ingestion.
