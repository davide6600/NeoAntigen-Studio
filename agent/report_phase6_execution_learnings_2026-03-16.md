# Phase 6 Execution Learnings

## Overview
Phase 6 focused on building a modern React + TypeScript frontend for the NeoAntigen-Studio, integrating backend observability (`structlog`, Prometheus), and establishing deployment artifacts (Docker Compose, Helm).

## Accomplishments
*   **Operational Security:** Replaced `os.getenv` with `pydantic-settings` to consolidate validation of all system secrets (database URLs, learning DB paths, mirror toggles) into `services/api/config.py`.
*   **Backend Observability:** Converted FastAPI and Celery worker logging to structured JSON using `structlog` for easier aggregation in Datadog/ELK. Added a `/metrics` endpoint to the API exposing the Prometheus ASGI app.
*   **Frontend Scaffold:** Initialized a Vite + React + TS workspace in `services/frontend`.
*   **Design System:** Built a custom Vanilla CSS design system using CSS tokens (`--bg-primary`, `--accent-primary`, etc.) to enforce a premium, dark-mode-first aesthetic without relying on external UI frameworks like Tailwind CSS, meeting the specific prompt constraints.
*   **Core UI Layout:** Implemented an Application Layout feature that guarantees the **Research Use Only (RUO)** banner is permanently visible, addressing biosecurity compliance constraints.
*   **Routing & Stubs:** Setup React Router to scaffold out the `Dashboard` (Job Monitoring), `Upload` (Sequence Submission), `Results` (Metric display), and `Approvals` (Human-in-the-loop) views.
*   **Deployment:** Created a multi-stage NGINX Dockerfile for the frontend. Integrated `frontend` into `docker-compose.yml` exposing ports locally to prioritize open-source developer experience. Scaffolded a basic Helm chart (`infra/k8s/neoantigen-studio`).

## Learnings & Patterns

1.  **Frontend Design Tokens:** 
    *   *Observation:* When restricted from using Tailwind CSS, establishing a `:root` variable configuration (`index.css`) immediately is crucial to avoid inline styles and ensure a cohesive "premium" look.
    *   *Action:* Extracted standard padding/margin (`--sp-4`), colors (`--bg-slate-900`), and border-radii into variables used uniformly across components.

2.  **Open-Source Port Exposure vs. Security:**
    *   *Observation:* Exposing Postgres, Redis, and MinIO ports locally in `docker-compose.yml` is contrary to strict internal security models, but vastly accelerates open-source adoption by allowing developers to plug in their native DB viewers.
    *   *Action:* Made the conscious trade-off to expose standard ports (5432, 6379, 9000/9001) in the local compose file, optimizing for contributor experience. This pattern should be documented in the repository's onboarding guide.

3.  **Vite Proxy for API Separation:**
    *   *Observation:* Setting up a `vite.config.ts` proxy is the cleanest way to avoid CORS issues during local UI development while the frontend runs on `localhost:5173` and the backend on `localhost:8000`.
    *   *Action:* Configured the proxy to map `/api` and `/metrics` directly to the `api` container/localhost port.

## Gaps & Next Steps
*   The API Client (`client.ts`) is currently a stub that isn't fully wired to genuine React Hooks (like `React Query` or `SWR`) for state caching.
*   The mock data used in `ResultsView.tsx` and `ApprovalsDashboard.tsx` needs to be replaced with live API calls.
*   The `docker-compose.yml` should be tested via a full integration smoketest.
