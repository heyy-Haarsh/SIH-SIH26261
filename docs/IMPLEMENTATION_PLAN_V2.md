# PRAMAN — Implementation Plan v2

Supersedes the "progress log" in `MASTER_IMPLEMENTATION_AUDIT.md`. Pass 1 was mostly cosmetic: it
re-labelled screens and derived "readiness" in the browser, while the workflow itself (submit gate,
finding lifecycle, clarifications, notifications) was unchanged. v2 is backend-first, one vertical
slice at a time.

## Definition of "done" (applies to every slice)

A feature is only counted as implemented when ALL of these hold:

1. Enforced on the **server** (a UI-only check does not count).
2. Persisted, with an Alembic migration **and** the dev additive-column list in `core/database.py`.
3. Exposed through an RBAC-checked route that has an entry in `tests/test_rbac_matrix.py`.
4. Wired into the UI in the role that uses it.
5. Covered by at least one backend test and one frontend test/typecheck.
6. Claims nothing the system cannot prove (decision-support only; simulated ≠ official).

## Baseline (verified, not assumed)

| Check | Before v2 | After baseline repair |
|---|---|---|
| Backend `pytest` | 13 failed / 334 passed | **347 passed**, 3 skipped |
| Frontend `tsc -b` | passes | passes |

Baseline findings (12 failures pre-dated pass 1; 1 was mine):

- **Real bug:** seeded demo apps `PRM-2025-1002/1003` had no assigned officer, so the demo officer
  could never see them (officers only see delegated apps). Fixed in `core/seed.py` (+ backfill).
- **Real bug:** officer `/applications/metrics` counted the whole region while the officer list was
  scoped to delegated apps. Metrics are now scoped identically (regional/admin still region-wide).
- Tests assumed one officer; auto-delegation load-balances. Tests now pin the assignee
  (`conftest.py`), except `test_delegation.py` which exercises the real balancer.
- Audit tests used a pre-rename category name; corrected to `admin`.
- My new `GET /applications/categories` and the existing `POST /scrutiny/transcribe` lacked RBAC
  policy entries; added.

## Gaps confirmed in code (what pass 1 did not touch)

| # | Gap | Evidence |
|---|---|---|
| G1 | No draft → submit gate; apps are created `SUBMITTED` and delegated immediately | `application_service.create_application` |
| G2 | No readiness API; "readiness" was browser-derived | no route; only `ApplicantDetailPage` logic |
| G3 | No notification model/API; bell is a static popover | no `notifications` model |
| G4 | Finding status is only `open/resolved/waived/accepted`; no history | `FindingStatus`, `resolve_finding` overwrites row |
| G5 | Replacing a document does not mark dependent findings superseded | `DocumentStatus.REPLACED` unused |
| G6 | A clarification links only one finding (`finding_ids[0]`) | `workflow_service.request_clarification` |
| G7 | Officer detail is tabbed, not a case workspace; no finding → page navigation | `officer/ApplicationDetailPage.tsx` |
| G8 | Processing is synchronous; no job record | `workers/tasks.enqueue` runs inline |
| G9 | Admin: no per-year requirements, no integrations honesty page | to be re-checked in S6 |

## Slices (in order; each ends green before the next starts)

### S1 — Draft → readiness → explicit submit  (G1, G2)
- `POST /applications` gains `save_as_draft` (default `false` so scripted/legacy clients and the
  existing test-suite keep working; the applicant UI always sends `true`).
- Draft applications: status `draft`, no `submitted_at`, **not delegated**, **hidden from officer /
  regional lists and metrics**; uploads allowed (extraction runs; status is unaffected).
- `GET /applications/{id}/readiness` (applicant): `mustFix`, `reviewRecommended`, `limitations`,
  `canSubmit`. Built only from the applicant-safe document check + requirement catalog.
- `POST /applications/{id}/submit`: blocked (422 `not_ready`) while `mustFix` is non-empty;
  **idempotent** — a second call returns the current state with `alreadySubmitted=true` and writes
  no second audit/delegation. Row-level guard prevents double submit races.
- UI: wizard saves a draft; detail page shows server readiness and a Submit button.

### S2 — Notifications  (G3)
- Table `notifications` (user_id, kind, title, body, application_id, created_at, read_at).
- Emitted server-side on: submitted (applicant + assigned officer), clarification requested,
  clarification answered / resubmitted, decision recorded, assignment.
- `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.
- TopBar bell shows the real unread count and list (in-app only; email/SMS stated as not configured).

### S3 — Finding lifecycle + transition history  (G4, G5)
- Add statuses `under_review`, `clarification_requested`, `superseded`, `reopened`.
- Table `finding_transitions` (finding_id, from, to, actor, reason, at) written for every change.
- `POST /findings/{id}/transition`; legal-edge table enforced server-side.
- Replacing a document marks findings keyed to the old version `superseded` and flags dependent
  verification/reconciliation as stale.

### S4 — Multi-finding clarifications  (G6)
- Table `deficiency_findings` (deficiency_id, finding_id). Request body accepts `finding_ids[]`;
  linked findings move to `clarification_requested`; response/resubmit moves them to `under_review`.
- Applicant view lists the linked items in plain language (still no scores/rule codes).

### S5 — Officer case workspace  (G7)
- Three panels: left document/application navigation + findings list, centre `PdfEvidenceViewer`,
  right evidence + lifecycle actions. Clicking a finding opens its document at the cited page and
  highlights the region when a bbox exists; otherwise it says "no region available".
- Verification dimensions shown separately; officer review checklist.

### S6 — Admin governance honesty  (G8, G9)
- Processing-job record for validation/verification runs (status, started/finished, error) shown to
  admin; integrations page states live vs simulated vs not configured.
- Re-audit rule lifecycle and category/year requirements before changing anything.

### S7 — Final verification
- Full backend + frontend suites, typecheck, build; role walkthrough; honest list of what is partial.

## Out of scope / will be reported as partial if not reached
Celery/async workers, email/SMS delivery, real government-source integrations, PDF text-layer
bounding boxes for non-OCR documents, production auth (demo header auth remains dev-only).

---

## Results (end of v2 pass)

| Check | Result |
|---|---|
| Backend pytest | **374 passed**, 3 skipped |
| Frontend itest | **67 passed** (12 files) |
| Frontend 	sc -b / ite build | clean / builds (one chunk-size warning) |
| Alembic | new heads 20261028_0010 (notifications), 20261028_0011 (finding lifecycle). Verified by stamping 0009, upgrade, downgrade, upgrade. A from-scratch `upgrade head` on SQLite still fails in an older, unrelated migration (`extracted_fields`); dev uses `create_all`. |

| Slice | Status | Notes |
|---|---|---|
| S1 draft → readiness → submit | **Done** | Server-enforced; idempotent submit; `test_submission_flow.py`, `ApplicantDetailPage.test.tsx` |
| S2 notifications | **Done (in-app only)** | Model, API, bell with unread count; email/SMS not configured and stated as such |
| S3 finding lifecycle + history | **Done** | 7 states, legal-edge table, `finding_transitions`, carry-over and supersede on re-validation |
| S4 multi-finding clarification | **Done** | `deficiency_findings`; applicant sees linked items in plain language |
| S5 officer case workspace | **Done (partial on checklist)** | Three panels; finding opens its document at the cited page; region highlight only for extracted fields that have coordinates; verification dimensions shown separately. No separate officer review-checklist widget yet |
| S6 admin governance | **Partly done** | `GET /admin/jobs` now reads real validation and extraction runs (the old endpoint was a stub returning `[]`); shown on System health. Integrations page already distinguishes live / simulated / not configured. Rule lifecycle and per-year requirements were not re-audited or changed |
| S7 verification | **Done** | This table |

### Known partials (not claimed as complete)

- Replacing a document supersedes findings only through the next validation run; verification and
  reconciliation records are not individually stamped stale. The "latest run wins" selection is
  what keeps old results from showing.
- A finding cites a page, not a region; regions come only from extracted fields with coordinates.
- Job view is derived from run records; there is still no worker queue.
- Demo header auth, no email/SMS, no real government-source integrations.
