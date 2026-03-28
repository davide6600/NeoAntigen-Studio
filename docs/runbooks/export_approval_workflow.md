# Export Approval Workflow Runbook

## Overview
To comply with strict Research Use Only (RUO) and biosecurity regulations, no synthesized sequence design (mRNA/peptide) can be exported without an explicit "Human-in-the-Loop" approval.

## The Workflow

### 1. Job Genesis and Design
*   A pipeline job successfully generates candidate sequences (`POST /jobs`).
*   The system proposes a synthesis design (`POST /mrna/design`). This automatically screens the sequence against known pathogen blacklists.
*   If safe, the system transitions to a `Pending Approval` state and generates an internal proposal token.

### 2. Officer Review
*   The **Biosecurity Officer** logs into the Frontend **Approvals Dashboard**.
*   They review the associated `variant_annotations`, `peptide_candidates`, and the algorithmic `safety_findings`.
*   They must verify the request context (e.g., verifying the requesting PI and the research protocol).

### 3. Execution of Approval
*   The Officer clicks "Approve" on the dashboard, which submits a signed RBAC token to `POST /mrna/export`.
*   **API Action:**
    *   The API validates the Officer's identity and token.
    *   The API generates the `.fasta` file.
    *   The API generates a highly structured `.manifest.json` sidecar. This manifest is cryptographically bound to the FASTA and explicitly records the Approver's name, timestamp, and the statement that the export is for RUO purposes only.
*   The files are successfully offloaded to the external synthesis provider or secure object storage bucket.

### 4. Handling Rejections
*   If the Biosecurity Officer clicks "Reject" or if a blacklist rule matches:
    *   The export is permanently halted.
    *   The Job status is updated to `Rejected`.
    *   The rationale and timestamp are immutably written to the `learnings`/audit tables.
