# PRAMAN System Architecture Diagrams (v1)

Presentation-ready architecture assets for **PRAMAN (SIH26261)**, drawn only from what is implemented in this repository (Phases 1–8). Application runtime code was not modified.

## Output files

| File | Format | Use |
|------|--------|-----|
| `praman-system-architecture-v1.html` | Editable HTML + embedded SVG (1920×1080, 16:9) | Open in browser; Print/PDF; Download SVG button |
| `praman-system-architecture-v1.svg` | Standalone SVG | PowerPoint Insert → Picture; vector edit in Inkscape/Illustrator |
| `praman-system-architecture-v1.png` | Raster PNG (16:9) | Direct PPT slide drop-in |
| `praman-system-architecture-v1.mmd` | Mermaid source | Revise structure later in any Mermaid-capable editor |

Absolute paths (workspace root `E:\SIH-SIH26261`):

- `E:\SIH-SIH26261\docs\design\architecture\praman-system-architecture-v1.html`
- `E:\SIH-SIH26261\docs\design\architecture\praman-system-architecture-v1.svg`
- `E:\SIH-SIH26261\docs\design\architecture\praman-system-architecture-v1.png`
- `E:\SIH-SIH26261\docs\design\architecture\praman-system-architecture-v1.mmd`
- `E:\SIH-SIH26261\docs\design\architecture\README.md`

## Legend (honesty labels)

### Implemented (solid blue)

- React + TypeScript + Vite frontend with Applicant / Officer / Admin role shells
- Live UI: applicant dashboard/apps/upload/deficiencies; officer queue/detail/comparison; admin users/categories/requirements/rules/audit/settings
- FastAPI `/api/v1` routers: applications, extraction, reconciliation, forensics, workflow, doc_verification, admin, health
- Demo RBAC via `X-Demo-Role` / `X-Demo-User-Id` (enforced server-side; not SSO)
- Document intelligence: intake, classify, PDF text, optional OCR, field extraction, evidence mapping, reconciliation, local forensics
- Three-layer verification engine with **independent** Layer 1 / Layer 2 / Layer 3 statuses
- Layer 1 config-driven rule validation (`verification_engine/layer1.py` + `configs/*.json`)
- Layer 2 local `pdf_signature` heuristics; optional Nominatim geocode when enabled
- Layer 3 review triggers, checks, JSON `scrutiny_report`, officer resolve/recommend/reject
- SQLite (demo) / SQLAlchemy models listed on the diagram; local `uploads/` storage
- Clarification → corrected upload → resubmit → revalidation feedback loop
- Explainable priority score (prioritization aid only)

### Simulated / demo (amber dashed)

- Demo role switcher / header auth (not production SSO)
- `[SYNTHETIC]` / `SYN-RULE-*` and Phase 7 Layer 1 document configs (not official AICTE APH text)
- `simulated_issuers/` FastAPI service (`:8001`) and HTTP connectors (`mode: simulated`) — results labeled `SIMULATED_RESULT`; `official_verification` is never claimed as live
- Application-level `MockVerificationAdapter` when live verification is off

### Planned / external-dependent (grey dotted)

- Celery / Redis async jobs (`USE_CELERY` — default local sync)
- MinIO object storage (default local filesystem)
- Authorized live AICTE / municipal / council connectors (return `SOURCE_UNAVAILABLE` if requested; no live connector in this build)
- LLM / AI extraction provider (`ENABLE_AI_EXTRACTION` reserved; local PDF/OCR does not require it)
- PDF/DOCX scrutiny report package export (JSON report exists on verification runs)
- Several frontend nav targets are PlaceholderPage only (e.g. standalone findings browser, PDF reports page, integrations page)

### Real optional externals (when configured)

- **Tesseract OCR** — real when installed on PATH and `ENABLE_LOCAL_OCR=true`
- **Nominatim (OSM)** — real HTTP geocode when `ENABLE_NOMINATIM_GEOCODE=true` (default off)

## Non-negotiable message on the diagram

> OCR success or Layer-1 rule PASS does **not** prove authenticity. Layer 1 ≠ Layer 2 ≠ Layer 3. The scrutiny officer retains the final decision.

## Regeneration notes

1. Edit `praman-system-architecture-v1.html` (primary visual) and/or `.mmd` (structural source).
2. Re-extract SVG via the page “Download SVG” button, or re-run the extract script used during generation.
3. Capture PNG from the HTML stage (browser screenshot at 1920×1080) after any visual edits.

## Validation basis (code / docs inspected)

- `docs/IMPLEMENTATION_STATUS.md`, `docs/ARCHITECTURE.md`, `docs/EXTRACTION.md`, `docs/SETUP.md`, `PLAN.md` resolved decisions
- `backend/app/main.py`, `api/routes/*`, `core/security.py`, `core/config.py`
- `document_processing/*`, `verification_engine/{pipeline,layer1,adapters,configs}`, `integrations/*`, `services/*`, `models/*`, `workers/tasks.py`
- `frontend/src/App.tsx`, `lib/nav.ts`, role pages under `pages/{applicant,officer,admin}`
- `simulated_issuers/` + `connector_registry.yaml`
