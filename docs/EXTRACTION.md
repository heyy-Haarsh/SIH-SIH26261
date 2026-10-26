# PRAMAN Document Intelligence (Phase 2)

## Pipeline

`Upload → Intake → Inspect → Classify (format + semantic) → PDF text / OCR → Field extraction → Evidence mapping → Persist → Validation`

## Feature flags

| Flag | Controls |
|------|----------|
| `ENABLE_LOCAL_PDF_EXTRACTION` | PyMuPDF digital text extraction |
| `ENABLE_LOCAL_OCR` | Tesseract OCR for scanned pages/images |
| `ENABLE_AI_EXTRACTION` | Optional LLM extraction only (not required; does **not** disable local PDF/OCR) |
| `AUTO_EXTRACT_ON_UPLOAD` | Run extraction automatically after upload |
| `OCR_LANGUAGES` | Comma-separated Tesseract langs (default `eng`; add `hin`,`mar` when traineddata installed) |
| `OCR_DPI` | Render DPI for PDF OCR |
| `MAX_EXTRACTION_PAGES` | Hard page cap |

## Coordinate convention

Bounding boxes use **PDF page points**, origin at the **top-left** of the page (`coordinate_space=pdf_page_points`). Image OCR boxes are converted approximately when rendered through PyMuPDF. If a location cannot be established, bbox fields remain `null` — never fabricated.

Confidence values:

- **OCR confidence** — from Tesseract word scores when OCR ran.
- **Field confidence** — `null` for deterministic regex/key-value (never fabricated).
- **Category confidence** — optional weak heuristic score, capped.
- These are **not** combined into a single compliance score.

## OCR setup (optional)

1. Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and add it to `PATH`.
2. Ensure `eng.traineddata` is installed (add `hin` / `mar` later as needed).
3. `pip install pytesseract pillow pymupdf`
4. Check: `GET /api/v1/extraction/ocr-capability`

If Tesseract is missing, digital PDF text extraction still works; scanned-only documents return `ocr_unavailable` / `requires_ocr` truthfully.

## API

- `POST /api/v1/documents/{id}/extraction-runs`
- `GET /api/v1/documents/{id}/extraction-runs/latest`
- `GET /api/v1/extraction-runs/{runId}`
- `GET /api/v1/extraction-runs/{runId}/fields`
- `POST /api/v1/extracted-fields/{fieldId}/corrections`
- `GET /api/v1/extraction/ocr-capability`

## Migration

```bash
cd backend
alembic upgrade head
```

Local demo also uses `create_all` on startup. For an existing SQLite file created before this phase, delete `praman_dev.db` or run Alembic.
