# Approval Logs Architecture

## Purpose
This document describes how the NeoAntigen-Studio captures structured human intent and approval tokens to enforce platform biosecurity and privacy governance.

## The `learnings` and `provenance_record` Architecture
NeoAntigen-Studio utilizes an immutable event pattern in the `learnings` database (alongside `provenance_record` in the Postgres SQL database) to archive all sensitive state changes.

### Auditable Events
The following actions cannot be executed autonomously and are securely logged:
*   `SEQUENCE_EXPORT_AUTHORIZED`
*   `SEQUENCE_EXPORT_REJECTED`
*   `MODEL_PROMOTION_AUTHORIZED`
*   `RETENTION_DELETION_AUTHORIZED`

### Anatomy of an Approval Log Record
When a designated Officer (e.g., Biosecurity Officer, Privacy Officer) issues a signed `POST` request to authorize an action, the API writes a comprehensive JSON log:

```json
{
  "event_type": "SEQUENCE_EXPORT_AUTHORIZED",
  "timestamp_utc": "2026-03-16T15:22:11Z",
  "actor_id": "bio-officer-991",
  "actor_role": "BIOSECURITY_OFFICER",
  "context": {
    "job_id": "job-4fa9b-11ee",
    "target_patient_id": "PT-001",
    "sequence_length": 1500,
    "mfe_score": -45.2,
    "safety_checks_passed": true,
    "statement_of_ruo": true
  },
  "rationale_provided": "Protocol verified. Target sequence matches IRB protocol #4421."
}
```

## Review and External Audit
*   All approval logs are persisted in PostgreSQL.
*   System administrators index these logs in external observability tools (like Splunk or Datadog) to provide compliance reports to internal Review Boards (IRB) or regulatory bodies.
