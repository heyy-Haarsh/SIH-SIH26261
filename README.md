# PRAMAN

AI-assisted **application validation**, document authentication support, and regulatory compliance workspace for AICTE problem statement **SIH26261**.

> **Core principle:** AI assists with extraction; deterministic rules evaluate formal requirements; authorized sources verify claims when configured; human officers decide. This repository does **not** claim live AICTE/government API access unless you configure authorized connectors.

## Repository structure

```
praman/
  frontend/           React + TypeScript + Vite + Tailwind
  backend/            FastAPI + SQLAlchemy + Alembic
  simulated_issuers/  Separate FastAPI simulated HTTP issuers (port 8001)
  docs/               Architecture, API contracts, integration research
  PLAN.md / DECISIONS.md
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- Optional: PostgreSQL, MinIO, Redis (not required for local demo)

## Quick start (local demo)

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env .env  # already present for local demo; or copy from ../.env.example

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/api/v1/health

The demo uses **SQLite** (`praman_dev.db`) with `USE_SQLITE_FALLBACK=true`. This is explicitly development-only. For PostgreSQL, set:

```env
DATABASE_URL=postgresql+psycopg://praman:praman@localhost:5432/praman
USE_SQLITE_FALLBACK=false
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

Use the **Demo** role switcher in the top bar to move between Applicant, Scrutiny Officer, and Administrator. It is **not** secure authentication; the API still enforces role headers and resource checks.

### 3. First working flow (seeded SIH scenarios)

1. Switch to **Applicant** — open **PRM-2025-1001** (mismatch / expired fire / unavailable payment source)
2. Or create a new application and upload under Phase 7 codes (`FIRE_NOC`, `AICTE_PAYMENT_RECEIPT`, …)
3. Switch to **Scrutiny Officer** → Queue → claim, run Verification / Forensics, request clarification
4. Applicant responds on **Deficiency Notices** → resubmit
5. Officer recommends/rejects with reasons (score is prioritization only)

Full script: [Demo walkthrough](docs/DEMO_WALKTHROUGH.md). Setup/env: [Setup](docs/SETUP.md).

> Fresh demo data: delete `backend/praman_dev.db` and restart the API so `seed_if_empty` reloads scenarios.

## Scripts

### Frontend

```bash
npm run dev
npm run typecheck
npm run build
```

### Backend

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

### Simulated issuers (optional HTTP Layer-2)

```bash
# from repo root — fails loudly if port busy (no silent port switch)
set SIMULATED_ISSUERS_PORT=8001
python -m simulated_issuers.main
```

Then set `USE_SIMULATED_HTTP_ISSUERS=true` and issuer base URLs in `backend/.env` (see `.env.example`).

### Synthetic evaluation

```bash
cd backend
python -m tests.synthetic.evaluate
```

## Roles

| Role | Purpose |
|------|---------|
| Institution / Applicant | Own applications, uploads, pre-checks, deficiencies |
| Scrutiny Officer | Queue, evidence review, findings, verification status, decisions |
| System Administrator | Users, rules, integrations, audit, health |

No additional application roles are defined.

## Documentation

- [Setup](docs/SETUP.md)
- [Demo walkthrough](docs/DEMO_WALKTHROUGH.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Document extraction / OCR](docs/EXTRACTION.md)
- [Integration research](docs/INTEGRATION_RESEARCH.md) (CCA trust roots, real APIs — research only)
- [PLAN.md](PLAN.md) · [DECISIONS.md](DECISIONS.md)

### Optional OCR (scanned PDFs / images)

```bash
# Install Tesseract OCR for your OS and ensure it is on PATH
# Then in the backend venv:
pip install pymupdf pillow pytesseract
```

Probe availability: `GET /api/v1/extraction/ocr-capability` (with demo auth headers).

Digital PDF text extraction works with PyMuPDF alone; OCR is optional.

## Security reminders

- Never commit `.env`, uploads, or identity documents
- Do not treat demo statistics as live AICTE data
- Synthetic rules are labeled `[SYNTHETIC]` until replaced with verified handbook clauses
