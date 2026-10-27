# SIH demo walkthrough (repeatable)

Seeded applications (after fresh DB start):

| App | Number | Story |
|-----|--------|--------|
| `app-1001` | PRM-2025-1001 | Mismatch + expired fire NOC + payment receipt with **unavailable** external source |
| `app-1002` | PRM-2025-1002 | Cleaner complete mandatory set (low priority) |
| `app-1003` | PRM-2025-1003 | Missing mandatory documents |

All `SYN-RULE-*` findings and Layer 1 configs are **synthetic**. External payment/fire/building/engineer/auditor checks return **SOURCE_UNAVAILABLE** (not fake verified).

## 0. Launch

```bash
# Terminal 1
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:5173. Confirm http://localhost:8000/api/v1/health shows `status: ok` and limitations.

**Test documents:** use generated pack `data/demo_pack/` (see `MANIFEST.json` + `README.md`). How verification works: `docs/HOW_VERIFICATION_WORKS.md`.

```bash
python scripts/generate_demo_documents.py
```

Optional Layer-2 simulation:

```bash
# Terminal 3 (repo root)
python -m simulated_issuers.main
# backend/.env → USE_SIMULATED_HTTP_ISSUERS=true
```

## 1. Applicant — see deficiencies / create upload

1. Role switcher → **Applicant** (lands on `/applicant`).
2. Dashboard shows seeded apps; open **PRM-2025-1001**.
3. Note L1/L2/L3 badges on documents if present; open **Clarifications & audit** if any open notices.
4. Optional: **New Application** → upload a PDF under `FIRE_NOC` or `AICTE_PAYMENT_RECEIPT`.

## 2. Officer — queue, claim, layers

1. Switch to **Scrutiny Officer**.
2. **Queue** → open **PRM-2025-1001**.
3. Tabs:
   - **Findings** — institution mismatch (synthetic)
   - **Reconciliation** — run if needed after live uploads
   - **Authenticity & Forensics** — local heuristics; not automatic fraud
   - **Verification** — **Run document verification**; payment/fire external = `source_unavailable`
4. **Start scrutiny** → claim the application.
5. Issue **clarification** with a clear title/body.

## 3. Applicant — respond & resubmit

1. Switch to **Applicant**.
2. **Deficiency Notices** or application banner → respond (≥5 chars).
3. Upload a corrected document (new version preserved).
4. **Resubmit** from the application page.

## 4. Officer — decision

1. Switch back to **Officer**.
2. Review evidence; resolve open checks with reasons (audited).
3. **Recommend** or **Reject** with a written reason (score is prioritization only).

## 5. Admin — config honesty

1. Switch to **Administrator**.
2. **Rules** — synthetic filter; official create without verified source fails validation.
3. **Audit** — search `workflow.` / `doc_verification.` / `admin.`.
4. **Settings** — verification toggles; secrets rejected.

## Talking points for judges

- Extraction assists; deterministic **synthetic** rules evaluate demo requirements; humans decide.
- Three verification layers are **independent** — rule pass ≠ authenticity.
- Unavailable sources are labeled `SOURCE_UNAVAILABLE`, never invented as verified.
- Prior document versions, findings, and audit events are preserved across resubmission.
