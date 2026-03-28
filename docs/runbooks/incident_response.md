# Incident Response Runbook

## Overview
This runbook defines the procedures for responding to operational, security, and biosecurity incidents within the NeoAntigen-Studio platform.

## Severity Levels
- **SEV-1 (Critical):** Data breach, biosecurity violation (unauthorized export of restricted sequence), or complete platform outage.
- **SEV-2 (High):** Major subsystem failure (e.g., Worker queue down, Nextflow executor failing repeatedly) blocking all jobs.
- **SEV-3 (Moderate):** Non-critical bugs, partial UI degradation, single-job failures.

## 1. Biosecurity Incidents (Unauthorized Export or Blacklist Hit Bypass)
If an unauthorized or highly dangerous sequence is generated or exported bypassing controls:
1. **Immediate Mitigation:** Shut down the worker nodes (`docker compose stop worker` / scale worker deployment to 0).
2. **Revoke Access:** Immediately rotate API secrets and invalidate all active session tokens/Approval Tokens.
3. **Audit Log Review:** Query the PostgreSQL `learnings` and `provenance_record` tables, and review JSON logs in Datadog/ELK for the specific job ID to trace the actor.
4. **Escalation:** Notify the **Biosecurity Officer** and **Security Lead** immediately. 
5. **Impact analysis:** Determine if the generated `.manifest.json` or `.fasta` files left the secure environment.

## 2. Infrastructure Failure (Workers/DB Down)
1. **Diagnostics:** Check Prometheus metrics (`GET /metrics`) to verify endpoint availability. Check `docker compose logs api` and `docker compose logs worker`.
2. **Database Connectivity:** If Postgres or Redis is unreachable, verify network settings and volume mounts.
3. **Queue Stalls:** If jobs are stuck in `Pending` state, restart the Celery workers. Verify the Redis broker is active. 

## 3. Data Integrity & PII Leaks 
1. **Quarantine:** Immediately restrict access to the offending Job API endpoints.
2. **Review:** Cross-reference `SequenceRun` and `Patient` tables to identify exposed data.
3. **Escalation:** Contact the **Privacy Officer** to execute emergency `Retention/Deletion` procedures on compromised data.
