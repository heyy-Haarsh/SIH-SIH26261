# How document verification actually works (as implemented)

No marketing filter — this is the real pipeline in code today.

---

## What “verifying” means here

PRAMAN does **not** declare a document authentic by itself. It runs **three independent layers** and keeps their statuses separate:

| Layer | Code | What it answers | What it does **not** answer |
|-------|------|-----------------|-----------------------------|
| **1 — Rules** | `verification_engine/layer1.py` + `configs/*.json` | Are required fields present? Do dates/formats/arithmetic look OK? | Authenticity / “is this a real government certificate?” |
| **2 — External / local adapters** | `adapters/*` + optional `simulated_issuers/` | Did an adapter return a status (signature heuristics, geocode, HTTP stub/simulated issuer)? | Live AICTE/municipal confirmation unless a real authorized API is wired |
| **3 — Review** | pipeline `_needs_review` + officer UI | Should a human look at this? | Automatic approve/reject of the application |

**Layer 1 PASS ≠ authentic.** The pipeline always appends a limitation stating that.

---

## End-to-end steps (what the code does)

### A. Upload (applicant)

1. Applicant selects a **requirement code** (e.g. `FIRE_NOC`, `AICTE_PAYMENT_RECEIPT`) and uploads a file (`pdf` / `txt` / images as allowed).
2. File is stored under `backend/uploads/`; a **document version** row is created (SHA-256, mime, path).
3. If `AUTO_EXTRACT_ON_UPLOAD=true` (default), extraction starts.

### B. Document intelligence (extraction)

Implemented in `app/document_processing/`:

1. **Intake / inspector** — empty/corrupt/unsupported → unreadable signals.
2. **Classification** — keyword heuristic category (may mismatch vs selected requirement).
3. **PDF text** (PyMuPDF) and/or **OCR** (Tesseract if installed + `ENABLE_LOCAL_OCR`).
4. **Field extraction** — deterministic `Key: Value` / aliases (`field_extractor.py`). Stores **raw value**; may also store `normalized_value` (transliteration) without overwriting raw.
5. Optional **LLM** only if `ENABLE_AI_EXTRACTION=true` and `LLM_PROVIDER=gemini|openai` — fills missing fields / explanations; **never pass/fail**.
6. Optional **QR** decode if `pyzbar` available — compare to extracted fields.
7. Fields saved as extracted-field rows linked to the document version.

### C. Cross-document reconciliation (application-level)

`reconciliation.py` (officer can trigger):

- Compares shared fields (e.g. institution name) across documents.
- Uses **normalized** values + **fuzzy** thresholds from config.
- Outcomes like MATCH / MISMATCH / MANUAL_REVIEW — not “fraud”.

### D. Local forensics (optional path)

`forensics` module / Phase 5 triage:

- Image/PDF heuristics (ELA, pHash, etc. when deps available).
- Labeled as **preliminary indicators requiring human verification** — never “forged”.

### E. Three-layer document verification (officer or applicant trigger)

API: `POST /api/v1/applications/{id}/document-verification`  
Code: `verification_engine/pipeline.py` → `run_for_document`.

For each document that has a JSON config (`get_config_for_requirement`):

1. Load **extracted fields** for the latest version.
2. **Layer 1** — `evaluate_layer1(config, fields)`  
   - Required fields, format checks, date checks, cross-field, arithmetic, conditional (as defined in that config).  
   - Rules are marked **`is_synthetic_rules: true`** in configs — demo rules, not official APH law.
3. **Layer 2** — for each adapter listed in `config.layer2.adapters`:
   - `pdf_signature` — local PDF signature / sigflags / pyHanko path if installed; scanned → `not_applicable`; empty trust store → integrity only + `chain_untrusted_no_trust_store` / manual review.
   - `geocode_nominatim` — only if `ENABLE_NOMINATIM_GEOCODE=true`.
   - `fire_certificate`, `aicte_payment`, `building_permission`, `engineer_credential`, `auditor_credential`, `affidavit_estamp`:
     - Default: **`SOURCE_UNAVAILABLE`** stub (`external_stubs.py`) — honest “no live API”.
     - If `USE_SIMULATED_HTTP_ISSUERS=true` **and** `simulated_issuers` is running: HTTP lookup against fixture keys (e.g. `FIRE-VERIFIED-001`). Responses are always **`mode=SIMULATED`**, **`official_verification=false`**. A “verified” simulated hit becomes **`SIMULATED_RESULT`**, not real official verification.
4. Aggregate Layer 2 statuses (never promote partial failures to fully verified).
5. **Layer 3** — if config `require_review_when` matches (rule fail, external unavailable, simulated, expired, signature invalid, …), create `REVIEW_REQUIRED` check; review status `pending`.
6. Persist `DocumentVerificationRun` + per-check rows + JSON `scrutiny_report`.

### F. Application workflow (human decision)

Separate from per-document layers:

1. Officer claims application → scrutiny.
2. May issue **clarification** (deficiency notice).
3. Applicant responds, may **re-upload** (new version), **resubmit**.
4. Officer recommends or rejects with a written reason.
5. Score/weights are **prioritization**, not auto-decision.
6. Audit events (and hash-chained audit log where Phase 7 is wired) record actions.

### G. Reports

`GET .../report.json` and `.../report.pdf` (Phase 8):

- Structured findings, REAL/SIMULATED labels, decision-support notice: final decision rests with the competent authority.

---

## Requirement codes that have Layer-1/2 configs

| Requirement code | Config file |
|------------------|-------------|
| `FIRE_NOC` | `fire_safety.json` |
| `AICTE_PAYMENT_RECEIPT` | `aicte_payment_receipt.json` |
| `OCCUPANCY_CERTIFICATE` | `occupancy_certificate.json` |
| `STRUCTURAL_STABILITY` | `structural_stability.json` |
| `SATELLITE_MAP` | `satellite_map.json` |
| `AUDITED_ACCOUNTS` | `audited_accounts.json` |
| `AFFIDAVIT_2` | `affidavit_2.json` |

Other codes (e.g. classic `AFFIDAVIT`, `LAND_OWNERSHIP`) still go through **extraction + reconciliation + workflow**; they may not have a Phase-7 three-layer config — pipeline returns no run for those.

---

## What is real vs simulated vs unavailable

| Capability | Status in this build |
|------------|----------------------|
| Text/OCR field extraction | **Implemented** (local) |
| Synthetic Layer-1 rules | **Implemented** (demo rules) |
| PDF signature heuristics / optional pyHanko | **Implemented** (no CCA certs bundled) |
| Nominatim geocode | **Optional** flag |
| Authority HTTP “verified” | **Simulated only** via `simulated_issuers` + flag |
| Live AICTE / fire / municipal / ICAI APIs | **Not connected** → `SOURCE_UNAVAILABLE` |
| LLM extraction | **Optional** via `.env` |
| Officer final decision | **Required** — system is decision-support |

---

## Fastest way to see Layer 1 vs Layer 2 in a demo

1. Upload `data/demo_pack/03_FIRE_NOC_missing_fields.txt` as `FIRE_NOC` → run verification → **Layer 1 fail**.
2. Upload `01_FIRE_NOC_pass.txt` as `FIRE_NOC` → run verification → **Layer 1 pass**, Layer 2 **`source_unavailable`** (default).
3. Start `python -m simulated_issuers.main`, set `USE_SIMULATED_HTTP_ISSUERS=true`, re-run on the pass file → Layer 2 **`simulated_result`** (still not official verification).
