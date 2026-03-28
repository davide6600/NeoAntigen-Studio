# Agent Bootstrap Report

## What was created

- Agent manifest, runtime README, and Python module scaffold.
- Dynamic skill registry with auto-discovery and DAG-based ordering.
- Skill skeletons for pipeline orchestration, ML retraining (staging), mRNA design/export gate, and label ingestion.
- Local context indexer (sqlite + deterministic local embeddings).
- Learnings datastore for model history, label ingestion events, acquisition batches, approvals, and audit logs.
- CI templates and GitHub workflow with unit tests and Nextflow smoke-test logic.
- Fast unit-test suite for each module.
- Proposal and approval protocol scaffolding.

## Local test command

```bash
python -m pip install -e .
pytest -q
```

## Nextflow smoke test

If Nextflow is installed:

```bash
nextflow run pipelines/nextflow/smoke_test/main.nf
```

If not installed, unit tests still run. Install Nextflow locally and run the command above to validate workflow execution.

## Manual staging retrain trigger

Example Python snippet:

```python
from agent.skills.ml_trainer import stage_retrain

proposal = stage_retrain(training_data_id="dataset-001", base_model_version="seq2neo-v1")
print(proposal)
```

This creates a staging model proposal only. Promotion to production requires explicit human approval and an approval record.
