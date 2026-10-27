# PRAMAN — final video script (tomorrow)

Print this or keep it on a second screen. Click in this order. **Do not stop the video if something fails** — every failure has a line to say and a next click.

**Length:** 8–12 minutes  
**URL:** http://localhost:5173  
**Role switch:** top bar — Applicant / Scrutiny Officer / Administrator (demo switch, not a login)

---

## 0. Start everything (before record)

Open **three** terminals. Leave them visible in a corner if a judge later asks.

```text
Terminal 1 — API
cd E:\SIH-SIH26261\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```text
Terminal 2 — UI
cd E:\SIH-SIH26261\frontend
npm run dev
```

```text
Terminal 3 — fake issuer (Layer 2 demo)
cd E:\SIH-SIH26261
backend\.venv\Scripts\activate
python -m simulated_issuers.main
```

Check in a browser tab (do not need to film this):

| URL | Must see |
|-----|----------|
| http://localhost:8000/api/v1/health | `"status":"ok"` |
| http://127.0.0.1:8001/health | `"simulated": true` |
| http://localhost:5173 | PRAMAN UI |

If port 8001 fails: continue the video anyway. Layer 2 will show **source unavailable** — that is still a demo beat (see Scene 2).

Keep Explorer open on:

`E:\SIH-SIH26261\data\demo_pack\`

Files you will upload:

| Order | File | Upload as |
|------|------|-----------|
| 1 | `12_AFFIDAVIT_name_A.pdf` | Affidavit |
| 2 | `14_LAND_name_mismatch.pdf` | Land / lease |
| 3 | `01_FIRE_NOC_pass.pdf` | Fire NOC |

Correction file (create on Desktop as `land_fixed.txt` before you record):

```text
Registered Lease Deed
Institution Name: Demo Institute of Technology
Trust Name: Demo Education Trust
Survey Number: 12/4
Land Area: 2.5 acres
Issue Date: 2021-01-01
```

Backup if create/upload dies: **Applicant → My Applications → PRM-2025-1001**.

---

## Scene 0 — 30 seconds (say this, then switch to Applicant)

> AICTE officers still read institution files by hand. PRAMAN is a scrutiny workspace: the applicant uploads, the system reads the file and flags issues, the officer decides. Three roles — applicant, officer, administrator. This demo uses a local issuer for Layer 2. It is not a live government API.

Point at the role dropdown. Switch to **Applicant**.

---

## Scene 1 — Applicant (2 minutes)

1. Sidebar **New Application**.
2. Type:
   - Institution: `Demo Institute of Technology`
   - Category: New Institution — Engineering
   - Programme: `B.Tech CSE`
   - Year: `2025-26`
3. Submit. Show the **required document list**.
   - Line: *The checklist is for this application type, not every document in India.*
4. Upload **12_AFFIDAVIT_name_A.pdf** as Affidavit. Wait. Point at type-match / clarity.
5. Upload **14_LAND_name_mismatch.pdf** as Land / lease.
6. Upload **01_FIRE_NOC_pass.pdf** as Fire NOC.
7. Scroll the list so the camera sees three files.

**If upload errors:** say *The server rejected this file; I will open a seeded application so we still see scrutiny.* Open **PRM-2025-1001**. Keep going.

**If type-match stays “not checked”:** refresh the page once. If still empty, keep going — officer view still has documents.

---

## Scene 2 — Officer (3 minutes)

1. Top bar → **Scrutiny Officer**. You should land on `/officer`.
2. **Application Queue** → open the app you just created (newest / your institution name).
3. Click **Start scrutiny** if it is shown.
4. **Issues** tab. Click one row so it **expands**. Read the title out loud. Point at “Applicant should…”.
   - Line: *Issues are grouped in plain language. The officer expands one, not a dump of rule codes.*
5. Click **Check with issuer** (header).
   - **If it works:** open the Fire NOC card. Layer 2 should show **simulated** for `FIRE-VERIFIED-001`.
     Line: *Certificate number went to our demo issuer. Labelled simulated — not AICTE live.*
   - **If it fails / source unavailable:** stay on the document pipeline. Point at Layer 2 **unavailable**.
     Line: *No authorized fire API is connected. The system reports unavailable instead of inventing verified.*
     That is still the feature. Do not apologize and stop.
6. **Documents** tab → click any card. Show: preview + pipeline (intake → OCR/class → Layer 1 → Layer 2 → Layer 3).
7. **Cross-document** tab. Affidavit name vs land deed name (`Demo Institute of Technology` vs `Completely Different College`).
   - **If empty:** say *Reconciliation needs both files; here is the Issues list instead.* Go back to Issues.
8. **Authenticity** tab.
   - Line: *Local file checks. A readable PDF is not proof it is genuine.*
9. **Review & decision**:
   - Request clarification.
   - Title: `Correct the land document institution name`
   - Body: `The land deed names Completely Different College. Replace it with a deed that names Demo Institute of Technology, matching the affidavit.`
   - Submit.

**If Start scrutiny is missing:** the app is already under scrutiny. Continue.

**If officer page is blank:** you are still Applicant in the top bar. Switch role, wait for redirect.

---

## Scene 3 — Applicant again (1 minute)

1. Top bar → **Applicant**.
2. **Clarifications** (or the application). Read the officer’s sentence on camera.
3. Open the application → replace the **land** file with `land_fixed.txt`.
4. Point at **version** (v2). Line: *The old file is kept.*
5. **Resubmit**.

**If Resubmit is blocked:** answer the clarification with any sentence longer than 5 characters, then resubmit.

**If replace fails:** upload the same `land_fixed.txt` from **Upload Documents** after picking this application.

---

## Scene 4 — Officer decision (1.5 minutes)

1. Officer → Queue → same application.
2. Issues / cross-document should look different. Line: *Current files only. History stays in audit.*
3. Expand one leftover issue if you want. Resolve with reason: `Reviewed against the replaced land deed.` (min 5 characters).
4. **Review & decision** → Recommend. Reason:

`Mandatory files are present. Institution name now matches on affidavit and land deed. Issuer check in this demo is simulated, so this is not official authenticity.`

5. **Download PDF report**. Open the PDF. Show page 1.

**If PDF fails:** stay on Review. The on-screen decision is enough. Say *Report download failed here; the decision is already recorded.*

---

## Scene 5 — Administrator (2 minutes)

Top bar → **Administrator**. Click every item below even if a panel is red.

1. **System Health** — point at API / database / OCR.  
   If Marathi is missing: *English OCR is installed. Marathi language data is not on this machine.*
2. **Integrations** — fire / payment / AICTE. Say **simulated** or **not configured**. Do not say “connected to AICTE”.
3. **Handbook References** — show the form.  
   If you have no handbook: *We do not type fake clause numbers. An admin verifies edition, section, page from the book.*
4. **Regulatory Rules** — open a `SYN-*` rule. *New versions do not rewrite old findings.*
5. **Audit Trail** — search your application number or `workflow`. Show upload, clarification, resubmit, decision.

If a page errors: screenshot the error, say *Admin API returned an error; next screen,* move on.

---

## 5-minute cut (if you are late)

1. Applicant: new app + three uploads.  
2. Officer: Issues expand + Check with issuer + clarification.  
3. Applicant: replace land + resubmit.  
4. Officer: recommend + PDF.  
5. Admin: Health + Audit.

---

## Lines when something is “not working”

| On screen | Say this, then continue |
|-----------|-------------------------|
| Backend unreachable | *API is down.* Restart terminal 1. Keep talking. |
| Source unavailable | *Honest result: no live issuer. Slot is still Layer 2.* |
| Simulated badge | *Demo issuer. Not official verification.* |
| Marathi / OCR degraded | *Tesseract is English-only on this PC after the last install.* |
| Empty handbook | *No invented AICTE clauses.* |
| Empty queue | Open **PRM-2025-1001**. |
| Role mismatch empty page | Switch the top-bar role. |
| Cannot resubmit | Answer the clarification first. |
| PDF fail | Show the on-screen decision. |

---

## Do not say

- “Verified by AICTE”
- “100% OCR / ML accuracy”
- “Production login”
- Any handbook section you did not save as verified

---

## Close (15 seconds)

> Applicant sees only their files and what to fix. Officer sees evidence and decides. Administrator configures rules. Unavailable stays unavailable. Simulated stays simulated.

Then stop recording.
