# PRAMAN — Project brief (for external review)

**Purpose of this file.** Hand this document to another model (or a reviewer) and ask for feature, UX, and product advice. It describes the system **as implemented in the repository today**, not the original plan. Advice should respect the design constraints in section 3. Do not recommend features that invent official AICTE verification, auto-approve applications, or call a document “forged.”

**Problem statement:** AICTE SIH26261.  
**Product name:** PRAMAN.  
**What it is:** A local decision-support workspace for institutional application scrutiny. Applicants upload documents. The system reads files, runs deterministic checks, optionally asks simulated or optional external sources, and presents issues to a human officer. The officer decides.

**Version posture:** Working SIH demo (SQLite + Vite). Not a production identity system and not a live government integration.

**How this brief was built.** Written from the codebase (routes, services, UI pages, configs, tests), then cross-checked against older docs. Several features below were **implemented in code but missing or under-described in `docs/IMPLEMENTATION_STATUS.md` / older architecture notes**. Those are called out with *[code feature, under-documented elsewhere]* so an advisor does not treat them as “ideas.”

---

## 1. One-paragraph summary

PRAMAN is a three-role web app (Applicant, Scrutiny Officer, Regional Officer) for reviewing institution approval documents. Upload triggers local extraction (PDF text, optional OCR, optional LLM). Officers see plain-language issues, a per-document five-stage report with in-page file preview, cross-document name/field mismatches, and local authenticity indicators. Two complementary engines run: (A) an application-level synthetic validation run for checklist / filename / classification / cross-identity findings, and (B) a config-driven three-layer verification engine for seven document types (rules → external/simulated adapters → human review). Scores only prioritize the queue. Final recommend / reject / clarification is always a human action with a written reason. Live AICTE, fire, municipal, ICAI, DigiLocker, and API Setu connectors are **not** connected. When a source is missing, the system returns “source unavailable” instead of “verified.”

---

## 2. Repository layout

```
frontend/            React 19 + TypeScript + Vite + Tailwind 4
backend/             FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2
simulated_issuers/   Separate FastAPI app (default port 8001) — fixture HTTP issuers
docs/                Architecture, API, demo script, this brief
data/demo_pack/      Synthetic key-value text + simple PDFs for demos
scripts/             Demo document generator
PLAN.md              Locked implementation plan (intent). Some items differ from code — see §17.
DECISIONS.md         Architecture decisions D-01 … D-21
```

Local demo:

| Piece | How to run | URL |
|-------|------------|-----|
| API | `cd backend` → venv → `uvicorn app.main:app --reload --port 8000` | http://localhost:8000 · docs at `/docs` |
| UI | `cd frontend` → `npm install` → `npm run dev` | http://localhost:5173 |
| Simulated issuers (optional) | from repo root: `python -m simulated_issuers.main` | http://127.0.0.1:8001/health |
| Database | SQLite `backend/praman_dev.db` when `USE_SQLITE_FALLBACK=true` | — |
| Auth | Demo header `X-Demo-Role` + top-bar role switcher | **Not** a login. `APP_ENV=production` refuses demo auth |

Fresh demo data: delete `backend/praman_dev.db` and restart the API so `seed_if_empty` reloads scenarios.

---

## 3. Non-negotiable design constraints

Advice that violates these is out of scope for this product.

1. **AI extracts and explains. Deterministic code decides pass/fail of rules.** An LLM never approves, rejects, or marks a document authentic. Rule “draft from text” is pattern matching, not an LLM publish path.
2. **Three statuses stay independent** on each document: rule validation, external verification, human review. A Layer 1 pass is not authenticity.
3. **Never claim verified from an unavailable source.** Missing API → `source_unavailable` (or equivalent), with a stated reason.
4. **Simulated results are labelled.** `mode=SIMULATED` forces `official_verification=false`. A simulated “verified” fixture is stored as `SIMULATED_RESULT`, not official confirmation.
5. **Forensics language is cautious.** Outputs are “preliminary indicator requiring human verification.” The product must not say “forged” or “fraud.”
6. **Rules in the demo are synthetic** until a human replaces them with verified handbook clauses. UI copy strips `[SYNTHETIC]` and shows plain language; handbook badges only render when a reference is marked verified and non-TODO.
7. **The officer decides.** Priority score and forensics triage score are queue aids only. They do not auto-recommend or auto-reject.
8. **No scraping, no CAPTCHA bypass, no bundled government certificates.** Real APIs are research-only in `docs/INTEGRATION_RESEARCH.md`.
9. **Degrade honestly.** Missing Tesseract, LLM key, pyHanko, QR library, or a down issuer must not crash the upload or invent a pass.
10. **Applicant APIs are narrow.** Applicant DTOs deliberately omit extracted fields, priority scores, forensic indicators, rule codes, and verification run codes. *[code feature]*

---

## 4. Status snapshot

### 4.1 Done and usable in the local demo

**Platform**

- Monorepo UI + API + simulated issuer service.
- Three roles with role-specific navigation and backend RBAC (`test_rbac_matrix`, demo header auth).
- Unified application **stages** shared by every dashboard so counts never disagree (`status_model.py`). *[code feature, under-documented elsewhere]*
- Synchronous job runner in-process (Celery/Redis/MinIO are hooks only).
- Structured API errors; no stack traces to clients.
- Backend pytest (~36 modules) + frontend Vitest (nav, scrutiny, admin).
- Seeded demo applications `PRM-2025-1001`, `1002`, `1003`.

**Applicant**

- Create application (institution name, category, programme, academic year).
- Category-driven checklist; upload and **replace** with version history (old bytes kept).
- Client-side validation (extension, size, MIME) + **blur/sharpness check** (Laplacian variance via pdf.js for PDF/JPEG/PNG) before upload. *[code feature]*
- Server intake: magic-byte sniff vs extension, empty/corrupt checks, size cap. *[code feature]*
- Auto-extract on upload (default); extraction failure does **not** erase the file.
- Type-match + clarity pre-check chips, with honest Marathi/Hindi OCR language notes when OCR is involved. *[code feature]*
- Clarifications list; respond; resubmit with blockers returned as messages.
- Applicant-readable status labels and a **whitelisted history** (internal audit actions never shown). *[code feature]*
- Correction list UI that turns officer clarification text into document → action rows. *[code feature]*

**Scrutiny officer**

- Dashboard metrics (same metrics function as regional overview).
- Live queue with priority; concurrent-claim guard (second officer blocked).
- Start scrutiny; Issues / Documents / Cross-document / Authenticity / Review & decision tabs.
- Plain-language issues (`issue_text.py`) with expand, “applicant should…”, layer, evidence, resolve (min reason length).
- **Speak** button — Sarvam STT (WebSocket realtime proxy + REST fallback); key stays on server; transcript editable. *[code feature]*
- **Document report side panel**: file preview + five-stage pipeline report for one document; Escape to close. *[code feature, under-documented elsewhere]*
- In-page **DocumentPreview** (PDF iframe / image / text slice) via authenticated blob fetch + path sandbox. *[code feature]*
- Handbook citation badge only when reference is verified (edition · section · page); never a guessed clause. *[code feature]*
- Cross-document comparison page (apps with open mismatches) + in-app reconciliation panel.
- Authenticity panel (forensics indicators with risk classes).
- Clarification (optional `finding_ids`), note, recommend, reject; refresh-summary endpoint.
- Download application PDF report; JSON report available via API.

**Regional officer**

- Users, categories, document requirements, settings.
- Versioned rules: draft → publish → reactivate → discard; usage counts.
- JSON **rule import** (validate then import as drafts only). *[code feature]*
- **Draft-from-text**: deterministic pattern match onto known logic (`missing_mandatory`, `filename_contains_expired`); **no AI call**; never auto-activates; citations mentioned in text stay unverified. *[code feature, under-documented elsewhere]*
- Handbook reference CRUD with completeness / verified status.
- Integrations catalogue with health check / enable toggle (does not invent live AICTE).
- System health roll-up (DB, storage, OCR, PDF extraction, signature, job runner, audit chain, rule engine, 24h activity). *[code feature]*
- Searchable audit + facets + CSV export + hash-chain verify.
- **Delegation**: load-balanced auto-assign, single and bulk delegate, officer load (active count, open issues, last assigned), configurable weights and max queue cap. *[code feature, under-documented elsewhere]*

**Document intelligence**

- Intake → inspect → format + semantic classify → PDF text / OCR → field extract → evidence map → persist.
- Raw value never overwritten; optional `normalized_value` (transliteration).
- Officer field corrections (`POST /extracted-fields/{id}/corrections`); later rules prefer corrected value.
- Optional LLM (Gemini/OpenAI) when flagged; fills missing fields only.
- Optional QR decode/compare (`pyzbar`).
- Server-side clarity assessment on images/PDF first page (`clarity.py`) plus client blur check.

**Cross-document & forensics**

- Fuzzy reconciliation (`rapidfuzz` + thresholds JSON); MATCH / MISMATCH / MISSING_DATA / POSSIBLE_DUPLICATE / MANUAL_REVIEW.
- Forensics: metadata, structure, signature heuristics, duplicates, ELA, pHash, hidden text, incremental-update abuse; weighted triage score; always “preliminary indicator.”

**Three-layer verification + issuers**

- JSON configs for seven requirement codes; Layer 1 arithmetic / conditional / format / date / required fields.
- Layer 2: PDF signature (sigflags + optional pyHanko), optional Nominatim, simulated HTTP issuers or honest unavailable stubs.
- Circuit breaker (closed / open / half-open) + tenacity retries; chaos flags on issuer service.
- Layer 3 review flags when config `require_review_when` matches.

**Reports & audit**

- Application `report.json` + `report.pdf` (ReportLab; Unicode font Nirmala on Windows when present).
- Per-document report API used by the side panel.
- Human-readable audit events + separate SHA-256 hash-chained `audit_chain_events`.

### 4.2 Implemented but limited on purpose

- Handbook references are admin-maintained pointers, not the official APH PDF. Many Layer 1 `aph_clause` values are `TODO`.
- Seed rules (`SYN-RULE-*`) are synthetic.
- Authority “verified” only via simulated issuer when enabled; default is unavailable stub.
- OCR, LLM, QR, pyHanko, imagehash/OpenCV, transliteration, Nominatim, Sarvam are optional.
- PDF report is ReportLab (plan said WeasyPrint); HTML template file still exists unused by the live path.
- Jobs are synchronous; no default Celery.
- Bounding boxes stored; **no** in-viewer highlight overlay.
- `EXTRACTION_TIMEOUT_SECONDS` is best-effort.
- No password / SSO / institution self-registration.

### 4.3 Not done

- Production auth (OIDC, real sessions).
- Live DigiLocker / API Setu / AICTE payment / fire / building / engineer council / ICAI APIs.
- Official APH text inside rules.
- In-viewer evidence bounding-box highlight.
- Background worker queue in the default demo.
- Multi-tenant notifications (email/SMS), eSign of officer decision, public applicant accounts.
- Mobile-native apps (web is desktop-first).

> Older `docs/IMPLEMENTATION_STATUS.md` is **stale** (still claims PDF export and several later phases are missing). Trust this brief and the code.

---

## 5. Two complementary check engines (easy to confuse)

| Engine | Trigger | Scope | Output |
|--------|---------|-------|--------|
| **A. Application validation run** | Upload auto-path / `POST .../validation-runs` / extraction with `run_validation_after` | Whole application: mandatory docs, file advisories, classification mismatch, synthetic regulatory rules | `ValidationRun` + `Finding` rows (e.g. `SYN-RULE-001`, `SYN-RULE-003`, `SYN-RULE-007`, `SYN-RULE-CLASS-001`) |
| **B. Three-layer document verification** | Officer “Check with issuer” / `POST .../document-verification` | Per document **with** a JSON config | `DocumentVerificationRun` + checks for Layer 1 / 2 / 3; statuses kept separate |

Both feed the officer **Issues** list after plain-language rewriting. Engine A covers documents that have **no** Phase-7 config (classic affidavit, land, affiliation, building plan). Engine B adds field-level rules and external/simulated adapters for the seven configured types.

---

## 6. Roles and screens

Demo switcher (top bar) sets the role and navigates home. The API still checks the role header and resource ownership.

| Role | Home | Can do |
|------|------|--------|
| Applicant | `/applicant` | Own applications only |
| Scrutiny Officer | `/officer` | Queue and decisions on unassigned / assigned-to-self apps |
| Regional Officer | `/admin` | Config, delegation, audit, health; can also open scrutiny |

There is no fourth role. Legacy stored value `admin` maps to `regional_officer`.

### 6.1 Unified stages (shared metrics)

*[code feature]* Every dashboard uses `backend/app/services/status_model.py` so “in queue” means the same thing everywhere.

| Stage | Meaning | Example DB statuses |
|-------|---------|---------------------|
| `draft` | Not submitted | `draft` |
| `awaiting_scrutiny` | Waiting for an officer | `submitted`, `processing`, `resubmitted`, `awaiting_review` |
| `under_scrutiny` | Officer working | `under_scrutiny`, `under_review`, `manual_review` |
| `awaiting_applicant` | Clarification outstanding | `clarification_required`, `deficiency` |
| `decided` | Terminal | `recommended`, `rejected`, `approved` |

Officer queue stages = `awaiting_scrutiny` + `under_scrutiny` only (apps waiting on the applicant are excluded from “my workload”).

Workflow statuses (current):  
`draft` → `submitted` → `processing` → `under_scrutiny` → `clarification_required` ↔ `resubmitted` → `recommended` | `rejected`

### 6.2 Applicant screens

| Screen | Route | Behaviour |
|--------|-------|-----------|
| Dashboard | `/applicant` | Own counts and recent list |
| My Applications | `/applicant/applications` | Status list |
| New Application | `/applicant/applications/new` | Institution, category, programme, year → checklist |
| Application detail | `/applicant/applications/:id` | Checklist, upload/replace, type/clarity chips, clarifications, history, resubmit, correction table |
| Upload Documents | `/applicant/uploads` | Pick app + requirement, upload, see pre-check |
| Clarifications | `/applicant/deficiencies` | Open deficiency notices |

**Privacy of applicant APIs** (`applicant_view_service.py`): *[code feature]*

- Returns applications, required documents, upload status, clarifications, final decisions, and officer notes the applicant should see.
- **Never** includes extracted fields, internal priority scores, forensic indicators, rule codes, or verification run codes.
- History is a whitelist of audit actions mapped to plain labels (e.g. “Document uploaded”, “Clarification requested”). Unknown actions are dropped.

**Applicant status copy examples:** Submitted → “Upload the required documents”; Clarification → “Action needed”; Recommended → next-stage wording; Rejected → show reason.

### 6.3 Document checklist (seed)

Categories: `NEW-ENG`, `EOA`, `INTAKE`, `NEW-MBA` — all currently share the same `DEFAULT_DOCS` list.

| Code | Name | Mandatory? | Three-layer JSON? |
|------|------|------------|-------------------|
| `AFFIDAVIT` | Sworn Affidavit | Yes | No |
| `LAND_OWNERSHIP` | Land Ownership / Lease Deed | Yes | No |
| `AFFILIATION` | University Affiliation Letter | Yes | No |
| `BUILDING_PLAN` | Building Plan Approval | Yes | No |
| `FIRE_NOC` | Fire Safety Certificate / NOC | No | Yes → `fire_safety.json` |
| `AICTE_PAYMENT_RECEIPT` | AICTE Payment Receipt | No | Yes |
| `OCCUPANCY_CERTIFICATE` | Occupancy / completion / Form D | No | Yes |
| `STRUCTURAL_STABILITY` | Structural Stability Certificate | No | Yes |
| `SATELLITE_MAP` | Satellite Map | No | Yes |
| `AUDITED_ACCOUNTS` | Audited statement of accounts | No | Yes |
| `AFFIDAVIT_2` | Affidavit 2 | No | Yes |

Allowed uploads: `pdf, png, jpg, jpeg, docx, txt`. Default max **25 MB**.

### 6.4 Scrutiny officer screens

| Screen | Route | Behaviour |
|--------|-------|-----------|
| Overview | `/officer` | Shared metrics |
| Application Queue | `/officer/queue` | Live list; badge for my queue |
| Application scrutiny | `/officer/applications/:id` | Main desk (tabs below) |
| Cross-document Review | `/officer/comparison` | Up to 25 apps, sorted by open mismatch count; links into each app |

Retired routes (`/officer/documents`, `/extracted`, `/findings`, `/verification`, `/decisions`, `/reports`) redirect to the queue — those concerns live **inside** one application.

**Scrutiny desk tabs**

1. **Issues** — grouped plain-language findings; expand for explanation, applicant action, layer, evidence; resolve with reason; Speak for dictation.
2. **Documents** — cards; open **Document report** side panel (preview + five stages).
3. **Cross-document** — reconciliation items; resolve / waive.
4. **Authenticity** — forensics indicators by risk class; resolve / waive.
5. **Review & decision** — start scrutiny, note, clarification (title + body, optional linked findings), recommend / reject with reason; score shown as prioritization only.

Header: **Check with issuer**, download PDF report.

**Who may act:** unassigned or assigned-to-self. Second officer → blocked. Regional Officer may delegate and may act on the scrutiny view.

### 6.5 Regional officer screens

| Screen | Route | Behaviour |
|--------|-------|-----------|
| Overview | `/admin` | Same application metrics |
| Delegation Queue | `/admin/delegation` | Unassigned apps, officer load, assign / bulk assign, weights + cap |
| System Health | `/admin/health` | Component health + limitations + 24h activity |
| Audit Trail | `/admin/audit` | Filters, facets, CSV, chain verify |
| Integrations | `/admin/integrations` | Catalogue, toggle, check |
| Regulatory Rules | `/admin/rules` | Versions, import, draft-from-text, publish |
| Handbook References | `/admin/handbook` | Upsert/delete clause pointers |
| Users & Roles | `/admin/users` | Create / edit / deactivate (three roles only) |
| Application Categories | `/admin/categories` | Codes + required-document sets |
| Document Requirements | `/admin/requirements` | Requirement catalogue |
| Settings | `/admin/settings` | Key/value runtime settings (loaded at startup) |

---

## 7. Upload, file safety, and applicant pre-check (detail)

*[Much of this was under-documented in older status docs.]*

### 7.1 Client (before bytes leave the browser)

1. Load upload policy from `GET /applications/upload-policy` (fallback mirrors backend defaults).
2. `validateFileMeta`: empty name, zero size, oversize, missing/disallowed extension, declared MIME vs extension.
3. Optional deeper checks: magic-byte kind detection helpers align with server kinds (`pdf|png|jpeg|docx|zip|text|unknown`).
4. **Blur check** (`blurCheck.ts`): for PDF (first up to 3 pages via pdf.js) and JPEG/PNG, compute Laplacian variance on a downscaled grayscale canvas. Threshold ≈ 90. Nearly blank pages (low content std) skip the “blurry” verdict. Message is advisory; server still accepts the file if policy allows.

### 7.2 Server intake

1. Size and extension enforced again.
2. Magic-byte sniff (`intake.sniff_kind`) vs extension and declared content-type; mismatches become failed or advisory file checks.
3. Store under `backend/uploads/` with hashed storage name; create `Document` + `DocumentVersion` (SHA-256, mime, path, version number).
4. Replace → new version; previous versions remain for audit and preview.
5. Path traversal prevented on download: resolved path must stay under upload root (`X-Content-Type-Options: nosniff`).

### 7.3 Type-match and clarity (applicant chips)

Built from the latest `ExtractionRun` (`document_check_service.py`):

| Signal | Values | Meaning |
|--------|--------|---------|
| Type match | match / mismatch / unclear / not_checked | Selected requirement vs semantic classifier |
| Clarity | clear / unclear / unreadable / not_checked | Readable text vs scan/OCR failure |

Also:

- Low average OCR confidence → unclear.
- Warnings prefixed `clarity:` from server clarity assessment can override.
- **Language note** when OCR was involved: Tesseract missing; Marathi pack missing; or Marathi enabled with the caveat that field extraction still works best on English/numbers. *[code feature]*

Copy always states this is a **pre-check**, not authenticity.

### 7.4 Correction table (applicant)

*[code feature]* `CorrectionTable` parses officer clarification / decision text into rows (`Document: action`) so the applicant sees a checklist of fixes instead of one opaque paragraph. Used on the applicant detail / clarification surfaces.

---

## 8. End-to-end workflows

### 8.1 Happy path

1. Applicant creates an application.
2. Checklist built from category.
3. If `AUTO_DELEGATE=true` (default), load-balancer assigns a scrutiny officer on submit.
4. Applicant uploads files (client + server checks).
5. Auto-extract (default); optional validation run after extraction.
6. Applicant sees type-match / clarity; may replace (v2…).
7. Officer **Start scrutiny** (`submitted` / `processing` / `resubmitted` → `under_scrutiny`).
8. Officer reads Issues; may run reconciliation, forensics, **Check with issuer**.
9. Clarification → applicant responds + optional replace → **Resubmit**; or Recommend / Reject with reason.
10. Audit events (+ chain events on verification). PDF/JSON report available.

### 8.2 Extraction pipeline (per file)

`document_processing/orchestrator.py`

1. Intake / inspector — empty, corrupt, encrypted, unsupported.
2. Format classification — digital / scanned / mixed PDF, image, text, docx, unreadable.
3. Semantic classification — keyword map (may disagree with selected requirement → type-match).
4. Text: PyMuPDF and/or Tesseract (`OCR_LANGUAGES`, default `eng+hin+mar`). Missing packs degrade honestly.
5. Field extractor — aliases including Hindi/Marathi; raw + optional `normalized_value`.
6. Optional LLM if enabled and fields still missing (`source=llm`).
7. Optional QR compare.
8. Persist run + fields; officer may correct a field.

### 8.3 Application validation run (Engine A)

`validation_service.py` + synthetic rule runtimes. Examples:

- Missing mandatory documents (`SYN-RULE-001` / `missing_mandatory`).
- Filename suggests expired (`SYN-RULE-003` / `filename_contains_expired`).
- Cross-document identity (`SYN-RULE-007`).
- Classification mismatch advisory (`SYN-RULE-CLASS-001`).
- File type / quality advisories.

Disabled or unpublished admin rules are skipped. Findings are explainable and resolvable by the officer.

### 8.4 Three-layer verification (Engine B)

`POST /applications/{id}/document-verification` → `verification_engine/pipeline.py`

For each document with a JSON config:

1. Load fields (corrected → normalized → raw).
2. **Layer 1** — required / format / date / cross-field / arithmetic / conditional. Pass ≠ authentic (limitation appended).
3. **Layer 2** — adapters:
   - `pdf_signature` — local; scanned → `not_applicable`; empty trust store → integrity only + `chain_untrusted_no_trust_store` / manual review.
   - `geocode_nominatim` — only if `ENABLE_NOMINATIM_GEOCODE=true`.
   - Fire / payment / building / engineer / auditor / e-stamp — stub `SOURCE_UNAVAILABLE` **or** HTTP simulated issuer → always `SIMULATED` / `official_verification=false`; fixture “verified” → **`SIMULATED_RESULT`**.
4. Aggregate Layer 2 with fixed priority (mismatch/expiry outrank clean simulated; unavailable + another definitive result → partial). Never promote partial to fully verified.
5. **Layer 3** — if `require_review_when` matches → review pending + review-required check.
6. Persist run, checks, JSON report snippet.

Documents without a config still use extraction, reconciliation, Engine A, and workflow — the three-layer runner does not invent a config.

### 8.5 Per-document five-stage report (officer UI)

*[code feature, under-documented elsewhere]*

API: `GET /applications/{id}/documents/{documentId}/report`  
UI: `DocumentReportPanel` (modal side panel) + `DocumentPreview`.

Stages (never merged into one authenticity light):

1. **Intake & clarity** — file checks, type match, clarity.
2. **OCR & classification** — content kind, predicted category, extraction status, optional field list toggle.
3. **Layer 1 rules** — rule findings / checks with handbook badge when verified.
4. **Layer 2 verification & reconciliation** — external adapter outcomes + cross-doc items involving this file; REAL / SIMULATED labels.
5. **Layer 3 evidence & officer review** — review-required items; resolvable checks.

Officer can resolve open checks from the panel; Escape closes. Preview reloads when version changes.

### 8.6 Reconciliation

Officer-triggered. Compares shared fields using normalized values + `rapidfuzz` thresholds (`reconciliation_thresholds.json`). Evidence should show original and normalized. Outcomes are comparison results, not fraud. Resolve / waive / accept; later rerun can mark old items cleared.

**Comparison page:** lists applications (capped) with open non-MATCH items, sorted by conflict count; banner reminds outcomes never label fraud.

### 8.7 Forensics

Separate run. Indicator codes include metadata anomaly, malformed structure, unusual modification, encryption, corrupt, signature absent/present/invalid, QR unavailable/not found/unverified, duplicate hash, near-duplicate, external claim simulated/unavailable, clean scan. Risk classes: informational, check_limitation, technical_anomaly, authenticity_concern, possible_duplicate. Triage score from `forensics_weights.json` — always preliminary.

### 8.8 Priority score

`scoring.py`, config `scrutiny-weights-v1`. Weighted open findings, reconciliation outcomes, forensics classes, missing mandatory docs, etc. Stored as `priority_score` for queue sort. Incomplete processing ≠ compliance. Does not change status alone.

### 8.9 Clarification ↔ resubmit

- Officer: title + description; may attach `finding_ids`.
- Creates `DeficiencyNotice` (open); status → `clarification_required`.
- Applicant responds (min length); may replace documents.
- Resubmit blocked until blockers clear (`resubmit_blockers`); on success → `resubmitted`.
- Officer reviews current files; prior versions remain in history/audit.

### 8.10 Reports

- `GET .../report.json` — structured result, REAL/SIMULATED, disclaimer if nothing officially confirmed.
- `GET .../report.pdf` — ReportLab; plain-language issues; decision-support footer; Unicode font when available.
- Permanent notice: *Decision-support output; final decision rests with the competent authority.*

### 8.11 Audit

| Store | Purpose |
|-------|---------|
| `AuditEvents` | Human-readable who/what/when; search, facets, CSV |
| `audit_chain_events` | Append-only SHA-256 chain (`prev_hash` → `chain_hash`); mode REAL/SIMULATED; `GET /admin/audit-chain/verify` |

### 8.12 Speech-to-text

*[code feature]* Officer Resolve / note controls. Browser → backend WebSocket proxy → Sarvam realtime; REST for short non-WebM clips. Key never in the browser. Empty `SARVAM_API_KEY` → clear “not configured.” Transcript editable; not a decision.

---

## 9. Delegation (load balancing)

*[code feature, under-documented elsewhere]*

`delegation_service.py`

**When:** on submit if `AUTO_DELEGATE=true`, or manually from the Delegation Queue (single / bulk).

**Eligible officers:** active users with role `officer`.

**Load signals per officer:**

- `active_count` — apps in active scrutiny statuses assigned to them.
- `open_issues` — open findings across those apps.
- `last_assigned_at` — for recency.

**Score (lower is better):**  
`active_count * active_count_weight + open_issues * open_issues_weight - hours_since_last * recency_weight`

Defaults: weights `3.0`, `1.0`, `0.5`; **`max_queue_cap` = 20**. Officers at or above cap are skipped. If none eligible, assignment fails with a clear error (no silent overflow).

Regional Officer can edit weights via `GET/PUT /admin/delegation/settings` (stored in `SystemSetting` key `delegation.weights`). Bulk delegate can take an explicit ID list or process the unassigned queue.

---

## 10. Rules admin, import, and draft-from-text

*[code feature]*

### 10.1 Lifecycle

Create rule → draft version → **publish** (re-validates definition) → optionally reactivate an older version → discard draft. Usage endpoint shows how often a rule appears in findings. Synthetic flag and handbook / verified-source refs are first-class fields.

### 10.2 JSON import

- Validate endpoint then import endpoint.
- Accepts a JSON array or `{ "rules": [...] }`.
- Max 100 items; aliases for common key spellings.
- **Imported rules are drafts / inactive** until an admin publishes. Nothing auto-activates.

### 10.3 Draft from text

- **Deterministic pattern matching only — no LLM.**
- Maps natural-language statements onto logics the engine actually implements (e.g. missing mandatory docs → `missing_mandatory` / `SYN-RULE-001`; expired filename keywords → `filename_contains_expired` / `SYN-RULE-003`).
- If the statement does not map, the API says so instead of inventing a rule.
- Any handbook citation mentioned in the text is flagged **unverified** and is **not** copied into official source fields.
- Output is a draft the admin must review and publish.

### 10.4 Handbook references & badges

- Admin CRUD for edition, section, page, title, notes, verified/complete status.
- Officer UI `HandbookBadge` renders **only** when status is verified, edition/section/page present, and note does not contain `TODO`. Otherwise nothing is shown — never a guessed clause. *[code feature]*

---

## 11. Three-layer document configs

Configs: `backend/app/verification_engine/configs/`. All synthetic / APH TODO. Adding a type ≈ one JSON + optional `connector_registry.yaml` entry.

| Config | Requirement | Layer 1 examples | Layer 2 |
|--------|-------------|------------------|---------|
| `fire_safety.json` | `FIRE_NOC` | Required fields, expiry | Fire issuer |
| `aicte_payment_receipt.json` | `AICTE_PAYMENT_RECEIPT` | Txn id, amount | Payment issuer |
| `occupancy_certificate.json` | `OCCUPANCY_CERTIFICATE` | License fields, dates | Building issuer |
| `structural_stability.json` | `STRUCTURAL_STABILITY` | Engineer fields; conditional hook | Engineer issuer |
| `audited_accounts.json` | `AUDITED_ACCOUNTS` | Arithmetic assets ≈ liabilities + equity | ICAI issuer |
| `satellite_map.json` | `SATELLITE_MAP` | Coordinates present | Nominatim (real, off by default) |
| `affidavit_2.json` | `AFFIDAVIT_2` | Signatory, date not future, stamp format | E-stamp issuer |

Registry maps connector name, `mode: simulated|real`, base URL env, timeout, retries, backoff, fallback `source_unavailable`, failure threshold, cooldown. Today every authority connector is `simulated`. Nominatim is the only `real` entry and stays off unless flagged.

Simulated issuer routes: fire-safety, building-occupancy, structural-engineer, aicte-payment, icai-membership, affidavit-estamp. Fixtures cover all six external statuses. Chaos: latency, jitter, `FORCE_OUTAGE` → 503 → source_unavailable (no crash), random 5xx, RPM limit. Busy port → **exit with error** (no silent port switch).

---

## 12. System health & integrations

*[code feature]*

**System health** rolls up:

- Core: database, file storage.
- Pipeline: PDF extraction, OCR, PDF signature capability, job runner.
- Infrastructure: audit chain integrity.
- Pipeline info: rule engine (active vs draft counts; synthetic limitation stated).
- Activity window (24h): applications by status, validation runs failed, extraction needs-attention, source_unavailable checks.

Each component returns health + **limitations** strings (e.g. “OCR language pack missing”, “demo rules are synthetic”).

**Integrations page** lists connector catalogue entries with mode and last check. Enabling a toggle does not magically attach a live government API; unauthorized sources still report unavailable / simulated.

---

## 13. Seeded demo data

| Application | Intent |
|-------------|--------|
| `PRM-2025-1001` | Name mismatch (affidavit vs land), expired fire NOC, payment external unavailable |
| `PRM-2025-1002` | Cleaner mandatory set |
| `PRM-2025-1003` | Missing mandatory documents |

Institution `DEMO-INST-001`. Users: applicant, two officers, one regional officer.

`data/demo_pack/` — paired `.txt` / simple `.pdf` (missing fields, expired fire, payment, unbalanced accounts, name mismatch). `scripts/generate_demo_documents.py` regenerates. More realistic PDFs under `data/` exercise OCR with partial field extraction.

Video script: `docs/DEMO_WALKTHROUGH.md`.

Simulated fixture keys (when issuers on): `FIRE-VERIFIED-001`, `FIRE-EXPIRED-001`, `TXN-VERIFIED-001`, `BLD-VERIFIED-001`, `ENG-VERIFIED-001`, `ICAI-VERIFIED-001`, `ESTAMP-VERIFIED-001`, etc.

---

## 14. API surface (grouped)

Prefix `/api/v1`. Interactive: http://localhost:8000/docs.

| Area | Operations |
|------|------------|
| Health | `GET /health` |
| Applications | list, create, get, metrics, upload-policy, upload document, validation-runs, `report.json`, `report.pdf` |
| Applicant | own list/detail (narrow DTO) |
| Extraction | OCR capability, start/get runs, fields, corrections |
| Reconciliation | run, latest, items, resolve |
| Forensics | run, latest, indicators, resolve |
| Document verification | configs, run app/doc, get run, resolve check |
| Workflow | start scrutiny, clarification, decision, notes, resubmit, refresh-summary, deficiencies respond, resolve finding |
| Scrutiny view | `scrutiny-review`, **per-document report**, document file bytes, `transcribe` + realtime WS |
| Admin | stats, institutions, users, categories, rules (+ versions, import, draft-from-text, usage), settings, audit (+ CSV, facets), audit-chain verify, handbook, integrations, system-health, officers/load, delegation queue, delegate, bulk-delegate, delegation settings |

---

## 15. Data the system remembers

Users, institutions, categories · Applications (status, priority score, assigned officer, institution name) · Documents + versions (hash, path, mime) · Extraction runs + fields (raw, normalized, corrected, page, bbox, source) · Validation runs + findings · Reconciliation runs + items · Forensics runs + indicators · Document verification runs + checks · Deficiency notices + review decisions · Regulatory rules + versions · Handbook references · Settings · Integration records · Audit events + audit-chain events.

Uploads on disk (`backend/uploads/`), not in DB. Alembic revisions `0001`–`0009` (extraction, reconciliation, forensics, scrutiny workflow, admin config, document verification, audit chain, institution name, handbook references).

---

## 16. Tech choices

| Concern | Choice |
|---------|--------|
| UI | React 19, React Router 7, Tailwind 4, Lucide, Recharts, pdf.js (preview + client blur) |
| API | FastAPI, Pydantic v2 |
| DB | SQLAlchemy 2; SQLite demo; PostgreSQL supported |
| Migrations | Alembic (+ `create_all` on local startup) |
| PDF text | PyMuPDF |
| OCR | pytesseract + Pillow; Tesseract binary external |
| PDF report | ReportLab |
| HTTP / retries | httpx, tenacity |
| Fuzzy match | rapidfuzz |
| Signatures | optional pyHanko; sigflags fallback |
| STT | Sarvam (REST + realtime WS proxy) |
| Tests | pytest; Vitest |
| Auth | `X-Demo-Role` → seeded users when `DEMO_AUTH_ENABLED=true` |

`requirements.txt` = always-on. Optional LLM/QR/transliteration: `requirements-optional.txt`. Dev: `requirements-dev.txt`.

### Notable feature flags / env

| Flag | Default intent |
|------|----------------|
| `DEMO_AUTH_ENABLED` | Local role headers; blocked in production |
| `USE_SQLITE_FALLBACK` | Dev SQLite |
| `AUTO_EXTRACT_ON_UPLOAD` | true |
| `AUTO_DELEGATE` | true |
| `ENABLE_LOCAL_PDF_EXTRACTION` / `ENABLE_LOCAL_OCR` | true |
| `OCR_LANGUAGES` | `eng+hin+mar` |
| `ENABLE_AI_EXTRACTION` / `LLM_PROVIDER` | off / `none` |
| `ENABLE_NOMINATIM_GEOCODE` | false |
| `USE_SIMULATED_HTTP_ISSUERS` | false (honest unavailable until enabled) |
| `TRUST_STORE_DIR` | empty (no CCA certs bundled) |
| `SARVAM_API_KEY` | empty until configured |
| `MAX_UPLOAD_MB` | 25 |

---

## 17. Plan vs code

`PLAN.md` phases 0–10 and D-01…D-21 are largely implemented (matching test files exist). Exceptions and extras:

| Plan / older docs | Code today |
|-------------------|------------|
| WeasyPrint PDF | ReportLab live path |
| “Administrator” role name | Regional Officer + delegation |
| (not in original plan) | Sarvam speech-to-text |
| (not in original plan) | Handbook admin + HandbookBadge |
| (not in original plan) | Rule import + deterministic draft-from-text |
| (not in original plan) | Load-balanced delegation weights / cap |
| (not in original plan) | Per-document five-stage report panel + preview |
| (not in original plan) | Client blur check; applicant narrow DTO; unified stages |
| (under-documented) | System health roll-up with limitations |
| Heavy deps in main requirements | Optional packages; core path degrades |

`docs/HOW_VERIFICATION_WORKS.md` matches the pipeline better than `docs/IMPLEMENTATION_STATUS.md` or the older half of `docs/ARCHITECTURE.md`.

---

## 18. Features implemented in code that older docs missed or undersold

Use this list when advising — these are **already built**, not wishlist items:

1. Unified application stages + shared metrics across officer and regional dashboards.
2. Narrow applicant DTOs and whitelisted applicant history.
3. Client blur/sharpness pre-check (pdf.js + Laplacian variance).
4. Server magic-byte intake + clarity assessment + Marathi/Hindi OCR language notes on chips.
5. Per-document five-stage report API and side panel with authenticated file preview.
6. HandbookBadge that refuses to show TODO / unverified citations.
7. Load-balanced delegation with configurable weights and queue cap; bulk assign.
8. Rule JSON import as drafts only; draft-from-text without LLM and without auto-publish.
9. Sarvam STT (realtime WS proxy + REST) for officer resolve reasons.
10. System health roll-up including audit-chain integrity and synthetic-rule limitation text.
11. Correction table parsing officer text into applicant action rows.
12. Comparison page aggregating open reconciliation conflicts across applications.
13. Dual engines: application validation findings **and** three-layer document verification.
14. Concurrent officer claim guards; refresh-summary; clarification can link finding IDs.
15. Demo banners on screens that need an honesty reminder (e.g. comparison).

---

## 19. Known product gaps (good targets for advice)

1. Official APH rules are not loaded; synthetic rules still drive demos.
2. Four mandatory seed docs lack three-layer JSON configs (affidavit, land, affiliation, building plan).
3. All categories share one checklist in the seed.
4. No in-document highlight of evidence bboxes.
5. Applicants get little field-level failure detail unless the officer writes a clarification.
6. Priority score can be misread as a fraud probability.
7. Demo auth will not survive a pilot.
8. Synchronous processing stalls on large scans.
9. Hindi/Marathi quality depends on installed tessdata + optional transliteration.
10. STT needs a Sarvam key and a microphone.
11. Reports lack signed officer attestation / public verification code.
12. No email/SMS when clarification is issued.
13. Duplicate detection is local corpus only.
14. Integrations UI must keep REAL vs SIMULATED impossible to miss.

---

## 20. What not to propose

- Auto-approve / auto-reject from score.
- “Genuine / forged” badges.
- Scraping government portals.
- Bundling or inventing CCA India roots.
- Treating simulated issuer hits as official verification.
- Letting an LLM publish a regulatory rule or override a deterministic check.
- Collapsing the three statuses into one green/red authenticity light.
- Claiming synthetic rules are the Approval Process Handbook.

---

## 21. Suggested questions for an advisor

1. Which missing Layer 1 configs (affidavit, land, affiliation, building plan) change a demo most, with fields that stay honest without official clauses?
2. How should the desk explain Layer 1 pass + Layer 2 source-unavailable so judges do not hear “verified”?
3. Keep priority score on the decision tab, move it to the queue only, or replace it with a “why high in queue” list?
4. Best applicant message for OCR missing / blurry scan / wrong type?
5. Clarification templates (officer-edited) vs free text for demo and real desks?
6. Smallest production-auth design that keeps three roles and the audit chain?
7. Which simulated issuer to show live, and which to leave unavailable for honesty?
8. What may a regional officer change in a rule without a developer, vs locked until handbook reference is verified?
9. Rank background jobs, email, and PDF highlights vs finishing official-rule content.
10. Which synthetic-evaluation metrics are safe to quote without over-claiming on real AICTE PDFs?
11. Should the five-stage document report be the primary officer view, with Issues as a summary?
12. How should draft-from-text be presented so judges do not think “AI wrote the regulation”?

---

## 22. File index (start in the code)

| Topic | Path |
|-------|------|
| API entry | `backend/app/main.py` |
| Settings / flags | `backend/app/core/config.py` |
| Seed data | `backend/app/core/seed.py` |
| Status enums | `backend/app/models/enums.py` |
| Unified stages | `backend/app/services/status_model.py` |
| Workflow | `backend/app/services/workflow_service.py` |
| Applicant narrow view | `backend/app/services/applicant_view_service.py` |
| Plain-language issues | `backend/app/services/issue_text.py`, `scrutiny_view_service.py` |
| Per-document report | `backend/app/services/document_report_service.py` |
| Priority score | `backend/app/services/scoring.py` |
| Delegation | `backend/app/services/delegation_service.py` |
| Rule import / draft-from-text | `backend/app/services/rule_import_service.py` |
| Handbook | `backend/app/services/handbook_service.py` |
| System health | `backend/app/services/system_health_service.py` |
| Extraction orchestration | `backend/app/document_processing/orchestrator.py` |
| Intake / magic bytes | `backend/app/document_processing/intake.py` |
| Clarity | `backend/app/document_processing/clarity.py` |
| Three-layer pipeline | `backend/app/verification_engine/pipeline.py`, `layer1.py` |
| Connectors | `verification_engine/configs/connector_registry.yaml`, `adapters/` |
| Simulated issuers | `simulated_issuers/` |
| PDF report | `backend/app/services/pdf_report_service.py` |
| Routes | `frontend/src/App.tsx`, `frontend/src/lib/nav.ts` |
| Officer desk | `frontend/src/pages/officer/ApplicationDetailPage.tsx` |
| Document report UI | `frontend/src/components/scrutiny/DocumentReportPanel.tsx`, `DocumentPreview.tsx` |
| Client blur / file policy | `frontend/src/lib/blurCheck.ts`, `fileValidation.ts` |
| Applicant detail | `frontend/src/pages/applicant/ApplicantDetailPage.tsx` |
| How verification works | `docs/HOW_VERIFICATION_WORKS.md` |
| Demo script | `docs/DEMO_WALKTHROUGH.md` |
| Real-API research | `docs/INTEGRATION_RESEARCH.md` |
| Decisions | `DECISIONS.md` |
