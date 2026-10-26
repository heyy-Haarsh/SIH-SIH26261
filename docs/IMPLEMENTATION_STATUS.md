# Implementation Status

## Working

- Monorepo frontend + backend scaffolding
- Three-role UI shell (sidebar, top bar, demo role switcher)
- Scrutiny Officer overview dashboard (synthetic mock stats)
- Application queue + application details (checklist, documents, findings, verification, audit tabs)
- Applicant dashboard, new application (API), document upload (API)
- Administrator system overview with live health probe
- FastAPI health, applications, documents, validation-runs, admin list endpoints
- Backend RBAC boundaries for the three roles
- File intake validation (extension, size, magic-byte warnings, SHA-256)
- Deterministic **synthetic** rules engine (`SYN-RULE-*`)
- Mock / local verification adapters with truthful statuses
- Alembic project layout; `create_all` + seed on startup for local demo
- Backend pytest suite; frontend typecheck/build scripts
- **Phase 2 document intelligence:** inspect → classify → PDF text (PyMuPDF) → OCR (Tesseract when installed) → deterministic fields → evidence mapping → extraction runs → validation
- Extraction APIs, OCR capability probe, Alembic migration `20261026_0001`
- Frontend detail page loads live API extraction fields (mock only for synthetic demo IDs)

## Mock / demo only

- Dashboard queue statistics (`frontend/src/mocks`)
- Rich application detail narrative data for IDs like `app-1001` in the UI mock layer when API has no row
- Demo role switcher (not real authentication)
- Synthetic regulatory rules (not official AICTE APH clauses)

## Not yet implemented / unavailable by design

- LLM extraction (`ENABLE_AI_EXTRACTION` reserved; local PDF/OCR work without it)
- Full DOCX structured extraction
- In-viewer bounding-box highlighting (page refs work; boxes stored for later)
- ML document classification
- Document forensics / tamper analysis
- Live AICTE or issuing-authority connectors
- MinIO / Redis / Celery (interfaces reserved; local adapters used)
- PDF scrutiny report export
- Full admin CRUD UIs for users, categories, rules
- Production PostgreSQL deployment hardening and IdP SSO

## Data retention (initial policy)

- Original uploads stored under `backend/uploads/` (gitignored)
- Extracted values and reviewer annotations stored separately from binaries
- Retention/deletion controls will be admin-configurable; until then, treat local uploads as ephemeral demo data and delete manually when finished
