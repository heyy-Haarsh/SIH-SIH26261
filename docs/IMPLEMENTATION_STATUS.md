# Implementation Status

## Working (Phases 1–8)

- Monorepo: React/Vite frontend + FastAPI/SQLAlchemy/Alembic backend
- Three-role demo shell with immediate role-home navigation
- Applicant: create application, upload (versioned), deficiencies, resubmit
- Officer: live queue/dashboard, application detail, scrutiny workflow, clarification/recommend/reject
- Phase 2 extraction: PDF text / OCR (when available), fields, extraction runs
- Phase 3 reconciliation with resolve + evidence
- Phase 4 local forensics (metadata/structure/signature heuristics, duplicates) — not automatic fraud
- Phase 5 explainable risk score + workflow statuses + audit
- Phase 6 admin CRUD: users, categories/requirements, versioned rules, settings, searchable audit
- Phase 7 three-layer document verification (configs + adapters + independent statuses)
- Phase 8 hardening: upload size capping, structured errors, concurrent officer guards, enriched demo seed, health limitations, docs
- Backend pytest suite; frontend typecheck/build

## Synthetic / unavailable by design

- `SYN-RULE-*` and Phase 7 Layer 1 configs are **synthetic demo rules**, not official AICTE APH text
- AICTE payment / building / fire / engineer / auditor adapters: **SOURCE_UNAVAILABLE** (no authorized connector)
- Demo header auth (`X-Demo-Role`) — not production SSO
- Nominatim geocode opt-in only (`ENABLE_NOMINATIM_GEOCODE`)
- LLM extraction reserved behind `ENABLE_AI_EXTRACTION` (local PDF/OCR work without it)

## Still limited

- No PDF/DOCX scrutiny report export (JSON scrutiny report on verification runs)
- No in-viewer bounding-box highlight (page refs stored)
- No MinIO/Redis/Celery in default demo (local sync)
- Full PKI certificate-chain validation not implemented (signature heuristics only)
- `EXTRACTION_TIMEOUT_SECONDS` configured; wall-clock enforcement is best-effort / platform-dependent

## Demo seed (fresh DB)

| Application | Intent |
|-------------|--------|
| PRM-2025-1001 | Mismatch + expired fire + payment unavailable external |
| PRM-2025-1002 | Cleaner complete mandatory set |
| PRM-2025-1003 | Missing mandatory documents |

See `docs/DEMO_WALKTHROUGH.md` and `docs/SETUP.md`.
