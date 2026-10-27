# PRAMAN setup

Local SIH demo stack (SQLite + Vite). **Not** a production identity deployment.

## Prerequisites

- Python 3.11+
- Node.js 20+ / npm
- Optional: Tesseract OCR (improves scanned PDF extraction; not required)

## Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Environment (copy from repo root `.env.example` into `backend/.env` if needed):

| Variable | Demo default | Notes |
|----------|--------------|--------|
| `APP_ENV` | `development` | Use `production` only with real secrets and **demo auth off** |
| `DEMO_AUTH_ENABLED` | `true` | Required for local role headers; **blocked** when `APP_ENV=production` |
| `USE_SQLITE_FALLBACK` | `true` | Dev only |
| `DATABASE_URL` | `sqlite:///./praman_dev.db` | Or PostgreSQL URL |
| `SECRET_KEY` | change-me… | Must be strong in production |
| `MAX_UPLOAD_MB` | `25` | Enforced on intake |
| `ALLOWED_EXTENSIONS` | `pdf,png,jpg,jpeg,docx,txt` | Magic-byte checked |
| `ENABLE_LIVE_VERIFICATION` | `false` | Stubs still return `SOURCE_UNAVAILABLE` |
| `ENABLE_NOMINATIM_GEOCODE` | `false` | Opt-in public geocoder (rate-limited) |
| `AUTO_EXTRACT_ON_UPLOAD` | `true` | Extraction failure does **not** erase the upload |

Migrations:

```bash
cd backend
alembic upgrade head
# If tables already exist from create_all: alembic stamp <revision> then upgrade
```

Start API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI: http://localhost:8000/docs  
- Health: http://localhost:8000/api/v1/health  

Fresh demo dataset: delete `backend/praman_dev.db` (and optionally `backend/uploads/`) then restart — `seed_if_empty` loads SIH scenarios.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` to `:8000`.

Demo headers sent by the UI: `X-Demo-Role`, `X-Demo-User-Id: demo-{role}`.

## Tests

```bash
cd backend
pytest -q

cd ../frontend
npm run typecheck
npm run build
```

## Honesty reminders

- `SYN-RULE-*` = synthetic demo rules, not official AICTE clauses  
- Layer 1 pass ≠ authenticity  
- Payment / building / fire / engineer / auditor adapters: **SOURCE_UNAVAILABLE** unless a real authorized connector is built  
- Demo auth is not SSO
