# Security Policy

## ⚠️ Research Use Only

NeoAntigen-Studio is a **Research Use Only (RUO)** platform. It is not intended for clinical, diagnostic, or therapeutic use. Security considerations described here relate to the protection of research data, biosecurity controls, and platform integrity.

---

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Current release |

---

## Reporting a Vulnerability

We take security seriously, especially given the biosecurity-sensitive nature of this platform.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report vulnerabilities by emailing **[INSERT SECURITY CONTACT EMAIL]**.

Please include:

1. **Description** of the vulnerability
2. **Steps to reproduce** (or a proof-of-concept)
3. **Impact assessment** — what could an attacker achieve?
4. **Affected component** (API, frontend, biosecurity gates, RBAC, pipeline, etc.)

### What to Expect

- **Acknowledgment** within 48 hours of your report
- **Initial assessment** within 5 business days
- **Resolution timeline** communicated after assessment
- **Credit** in the security advisory (if desired)

### Biosecurity-Specific Concerns

If your report involves:

- **Bypass of sequence export approval gates** — Priority: Critical
- **Bypass of biosecurity blacklist scanning** — Priority: Critical
- **Unauthorized access to patient-adjacent data** — Priority: Critical
- **RBAC/approval token forgery or escalation** — Priority: High
- **Audit log tampering or suppression** — Priority: High

These will be treated with the highest urgency and escalated to the designated Biosecurity Officer.

---

## Security Architecture

NeoAntigen-Studio implements multiple layers of security:

- **HMAC-signed approval tokens** for all gated actions (sequence exports, model promotion, data deletion)
- **Role-Based Access Control (RBAC)** with named approver roles (Biosecurity Officer, PI, ML Lead, Privacy Officer)
- **Immutable audit logging** in PostgreSQL for full provenance traceability
- **Biosecurity sequence scanning** against a maintained blacklist before any export
- **No external network calls by default** — all processing runs on local infrastructure

For details, see [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/compliance/`](docs/compliance/).

---

## Disclosure Policy

We follow a coordinated disclosure model:

1. Reporter submits vulnerability privately
2. We confirm, assess, and develop a fix
3. Fix is released
4. Advisory is published with credit to the reporter (if desired)

We ask reporters to allow a reasonable window (typically 90 days) for us to address the issue before any public disclosure.
