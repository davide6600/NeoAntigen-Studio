# Agent Bootstrap

This folder contains the bootstrap scaffold for the NeoAntigen Project Agent.

## Run locally

1. Create and activate a Python 3.12 environment.
2. Install dependencies:

```bash
python -m pip install -e .
```

3. Run tests:

```bash
pytest
```

## Safety and approval workflow

- Research Use Only (RUO).
- No autonomous wet-lab operations.
- Any sequence export intended for synthesis must call `safe_export` and requires explicit approval token: `APPROVE: <proposal_id>`.
- Sensitive actions must be described in `agent/proposals/proposal.md` and logged to audit events.

## QA & Debugging Mindset

- **Fix the Root Cause, Not Just the Symptom**: Do not limit debugging sessions to merely catching exceptions, displaying alerts, or failing gracefully. The primary goal is to ensure the actual features and functions work regularly. Users MUST be able to complete their intended workflows (e.g., CRUD operations, computations, UI interactions) completely error-free.
- **Error Handling as a Secondary Net**: Alerts and error flags (like `ApiErrorBanner` or `catch` blocks) are fallbacks for unpredictable network issues, NOT substitutes for fixing broken underlying data flows, N+1 query timeouts, or state mismatches.

## Startup behavior

On startup, the agent indexes `ARCHITECTURE.md`, `README.md`, optional `docs/*.md`, and the last 20 git commit messages, then surfaces:

- repository version,
- top 5 active skills,
- last 5 learning records,
- pending approvals and exact next-action strings.

At the end of each session that changes docs, learnings, governance notes, or startup behavior, update `DOC_INDEX.md` to keep the documentation map current for future sessions.
