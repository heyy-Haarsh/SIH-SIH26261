# PRAMAN Architecture

PRAMAN (SIH26261) is an AI-assisted platform for institutional application scrutiny, document authentication support, and regulatory compliance checks.

## Core principle

- **AI** assists with extraction and explanation when configured.
- **Deterministic rules** evaluate formal requirements (versioned).
- **Authorized external sources** verify claims when connectors are configured.
- **Human officers** make regulatory decisions.

No component silently invents AICTE handbook rules or fabricates live verification results.

## Monorepo layout

- `frontend/` — React + TypeScript + Vite + Tailwind UI
- `backend/` — FastAPI + SQLAlchemy + Alembic API and validation pipeline
- `docs/` — Architecture, API contracts, implementation status

## Frontend

- Role-specific navigation for **Applicant**, **Scrutiny Officer**, and **Administrator** only
- Demo role switcher (clearly labeled) — not secure authentication
- Mock statistics isolated in `src/mocks/` for dashboard demos
- Live create/upload flows call `/api/v1` when the backend is running

## Backend

- FastAPI routers under `/api/v1`
- SQLAlchemy models for users, institutions, applications, documents, rules, validation runs, findings, verifications, audit events
- Backend-enforced RBAC via `X-Demo-Role` resolution to seeded users (development)
- SQLite development-only fallback (`USE_SQLITE_FALLBACK=true`); PostgreSQL intended for production

## Document validation pipeline

Modular interfaces:

1. Intake / file pre-checks (implemented)
2. Classification (basic requirement-code passthrough)
3. OCR / extraction (unavailable unless configured)
4. Cross-document reconciliation (skipped without extractions fields)
5. Deterministic synthetic rules engine (demo rules labeled `[SYNTHETIC]`)
6. Forensics (unavailable stub)
7. External verification adapters (mock / local integrity)
8. Findings aggregation + priority aid score
9. Human review (API/UI hooks)
10. Scrutiny report generation (not yet exporting packages)

Local demo runs the pipeline **synchronously**. Redis/Celery and MinIO adapters are designed for later connection without rewriting core flows.

## Security notes

- Upload type/size checks and private upload directory
- CORS restricted to configured origins
- Secrets via environment variables
- Audit events for create/upload/validation
- Minimal logging of personal data; do not log full document contents
