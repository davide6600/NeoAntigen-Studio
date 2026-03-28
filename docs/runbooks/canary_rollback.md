# Canary Rollback Runbook

## Overview
This runbook covers the procedure for rolling back ML models (e.g., Seq2Neo or MHC ensemble predictors) if a new deployment exhibits performance degradation or concept drift.

## Triggers for Rollback
*   Automated drift detection alerts indicate significant changes in output distributions compared to the historical baseline.
*   Clinical or wet-lab feedback identifies a higher-than-expected false positive threshold.
*   The staging MLflow model promotion caused immediate pipeline failures.

## Rollback Procedure (MLflow API)

### 1. Identify the Degraded Model
Identify the currently active production model ID and the previous stable model ID. This information is available in the MLflow Model Registry or via the API audit logs.

### 2. Execute Rollback via API
Use the authenticated rollback endpoint to safely revert the model label.

```bash
# Example: Rolling back a failed Seq2Neo deployment
curl -X POST http://localhost:8000/models/seq2neo/production/rollback \
  -H "Authorization: Bearer <ML_LEAD_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Detected 15% drop in binding affinity precision.", "fallback_version": "v1.2.0"}'
```

### 3. Verify Rollback
Check model status to ensure the previous version is now serving requests:
```bash
curl -X GET http://localhost:8000/models/seq2neo/status
# Ensure output indicates "v1.2.0" is active in "production"
```

### 4. Post-Incident Review
*   Pause the automated retraining cron jobs (`stage_retrain`).
*   The **ML Lead** must analyze the failing model artifacts to determine if the training data was poisoned or if the hyperparameters overfit the recent ingestion labels.
