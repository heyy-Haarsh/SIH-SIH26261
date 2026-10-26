# PRAMAN

AI-assisted **application validation**, document authentication support, and regulatory compliance workspace for AICTE problem statement **SIH26261**.

> **Core principle:** AI assists with extraction; deterministic rules evaluate formal requirements; authorized sources verify claims when configured; human officers decide. This repository does **not** claim live AICTE/government API access unless you configure authorized connectors.

## Repository structure

```
praman/
  frontend/     React + TypeScript + Vite + Tailwind
  backend/      FastAPI + SQLAlchemy + Alembic
  docs/         Architecture, API contracts, status
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

### 3. First working flow

1. Switch to **Applicant**
2. Open **New Application** → create (calls API)
3. Open **Document Uploads** → paste the application id → upload a PDF
4. Backend runs file checks + synthetic rules and returns findings
5. Switch to **Scrutiny Officer** → Overview / Queue → open an application for the full details UI (mock-enriched demo records)

## Scripts

### Frontend

```bash
npm run dev
npm run typecheck
npm run build
```

### Backend

```bash
pytest -q
uvicorn app.main:app --reload --port 8000
```

## Roles

| Role | Purpose |
|------|---------|
| Institution / Applicant | Own applications, uploads, pre-checks, deficiencies |
| Scrutiny Officer | Queue, evidence review, findings, verification status, decisions |
| System Administrator | Users, rules, integrations, audit, health |

No additional application roles are defined.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Document extraction / OCR](docs/EXTRACTION.md)

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
