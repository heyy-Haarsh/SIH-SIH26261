# PRAMAN API Contracts (v0.1)

Base URL: `/api/v1`

Development auth headers (when `DEMO_AUTH_ENABLED=true`):

- `X-Demo-Role`: `applicant` | `officer` | `admin`
- `X-Demo-User-Id`: opaque demo label (identity resolved server-side from seeded users)

JSON responses use **camelCase** field names.

## Health

`GET /health` — public

```json
{
  "status": "ok",
  "environment": "development",
  "database": "sqlite (development-only fallback)",
  "storageBackend": "local",
  "demoAuth": true
}
```

## Applications

| Method | Path | Roles | Notes |
|--------|------|-------|-------|
| GET | `/applications` | applicant, officer, admin | Applicant scoped to own institution |
| POST | `/applications` | applicant | Body: `category_code`, `program_name`, `academic_year` |
| GET | `/applications/{id}` | applicant*, officer, admin | *own institution only |
| POST | `/applications/{id}/documents` | applicant, admin | multipart: `file`, `requirement_code` |
| POST | `/applications/{id}/validation-runs` | applicant, officer, admin | Runs deterministic pipeline |

### Upload response

```json
{
  "documentId": "...",
  "validationRunId": "...",
  "findings": [],
  "fileChecks": {
    "ok": true,
    "errors": [],
    "warnings": [],
    "sha256": "...",
    "source": "local_validation"
  }
}
```

## Admin

| Method | Path | Roles |
|--------|------|-------|
| GET | `/admin/users` | admin |
| GET | `/admin/rules` | admin, officer |
| GET | `/admin/audit` | admin |
| GET | `/admin/jobs` | admin |

## Verification honesty

Verification objects always include:

- `status` — e.g. `source_unavailable`, `verified_by_source`, `simulated_result`
- `source` — `authorized_live` | `local_validation` | `simulated_dev` | `manual_reviewer`

Live AICTE/government results are never fabricated.
