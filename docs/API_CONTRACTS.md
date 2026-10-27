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
  "demoAuth": true,
  "appVersion": "0.1.0",
  "maxUploadMb": 25,
  "limitations": ["…honesty banners…"]
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
  "extractionRunId": "...",
  "extractionStatus": "completed",
  "findings": [],
  "fileChecks": {
    "ok": true,
    "errors": [],
    "warnings": [],
    "sha256": "...",
    "source": "local_validation"
  },
  "pipelineOk": true,
  "pipelineWarnings": []
}
```

`pipelineOk=false` / `pipelineWarnings` means extraction or validation did not fully succeed after a file was accepted — never treat as authenticity or compliance.

## Workflow / scrutiny (Phase 5)

| Method | Path | Roles |
|--------|------|-------|
| POST | `/applications/{id}/scrutiny/start` | officer, admin |
| POST | `/applications/{id}/scrutiny/clarification` | officer, admin (assigned officer) |
| POST | `/applications/{id}/scrutiny/decision` | officer, admin (assigned officer) |
| POST | `/applications/{id}/resubmit` | applicant |
| GET | `/deficiencies` | authenticated (applicant scoped) |

## Document verification (Phase 7)

| Method | Path | Roles |
|--------|------|-------|
| GET | `/document-verification/configs` | authenticated |
| POST | `/applications/{id}/document-verification` | applicant, officer, admin |
| GET | `/applications/{id}/document-verification` | authenticated |
| POST | `/document-verification-checks/{id}/resolve` | officer, admin |

Per-document statuses on `documents` / runs: `ruleValidationStatus`, `externalVerificationStatus`, `reviewStatus` (independent; L1 pass ≠ authenticity).

## Admin (Phase 6)

| Method | Path | Roles |
|--------|------|-------|
| GET/POST/PATCH | `/admin/users` | admin |
| GET/POST/PATCH | `/admin/categories` | admin (GET also officer) |
| GET/POST/PATCH | `/admin/rules` (+ versions/publish/reactivate) | admin (GET also officer) |
| GET/PUT | `/admin/settings/{key}` | admin |
| GET | `/admin/audit` | admin (filterable) |

## Extraction

| Method | Path | Roles | Notes |
|--------|------|-------|-------|
| POST | `/documents/{id}/extraction-runs` | applicant, officer, admin | Body: `{force, run_validation_after}` |
| GET | `/documents/{id}/extraction-runs/latest` | any authenticated | Latest run + fields |
| GET | `/extraction-runs/{runId}` | any authenticated (resource-scoped) | |
| GET | `/extraction-runs/{runId}/fields` | any authenticated (resource-scoped) | |
| POST | `/extracted-fields/{fieldId}/corrections` | officer, admin | Body: `{corrected_value}` |
| GET | `/extraction/ocr-capability` | any authenticated | Truthful Tesseract status |

Upload response may include `extractionRunId` and `extractionStatus` when `AUTO_EXTRACT_ON_UPLOAD=true`.

## Verification honesty

Verification objects always include:

- `status` — e.g. `source_unavailable`, `verified_by_source`, `simulated_result`
- `source` — `authorized_live` | `local_validation` | `simulated_dev` | `manual_reviewer`

Live AICTE/government results are never fabricated.
