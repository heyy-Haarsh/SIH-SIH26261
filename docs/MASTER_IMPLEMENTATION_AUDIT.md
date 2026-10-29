# PRAMAN — Master implementation audit & plan

**Date:** 2026-10-28  
**Scope for this pass:** Phases 0–3 (audit → shell/nav → applicant journey → officer evidence workspace).  
**Jobs:** Keep synchronous processing; improve stage/progress UI. Celery deferred.  
**Source of truth:** Repository code (not stale status docs).

---

## 1. Existing architecture

```
frontend/  React 19 + Vite + Tailwind 4 + React Router 7
backend/   FastAPI + SQLAlchemy 2 + Alembic (head 20261028_0009)
simulated_issuers/  Optional HTTP Layer-2 fixtures (port 8001)
```

**Roles:** `applicant` | `officer` | `regional_officer` (UI “Regional Officer”; older docs said Administrator).

**Auth:** Demo headers `X-Demo-Role` / `X-Demo-User-Id`. Not production SSO.

**Dual check engines:**

| Engine | Unit | Output |
|--------|------|--------|
| A. `validation_service` | Application | `Finding` rows (SYN-RULE-*, classification, etc.) |
| B. `verification_engine` | Document (JSON config) | Layer1/2/3 `DocumentVerificationCheck` |

Officer Issues merge both via `scrutiny_view_service`.

**Stages (shared metrics):** draft → awaiting_scrutiny → under_scrutiny → awaiting_applicant → decided (`status_model.py`).

---

## 2. Functional features (preserve)

- Application create/submit, assignment (auto-delegate + load weights), concurrency claim guards.
- Upload: client validation + blur check; server magic bytes; versioning; secure preview.
- Extraction: PDF text, optional OCR (eng/hin/mar), fields with raw/normalized/bbox, corrections.
- Engine A + Engine B; reconciliation; forensics; priority score (queue aid only).
- Clarification ↔ respond ↔ resubmit; recommend/reject with reasons.
- Reports JSON/PDF; audit events + hash chain; handbook refs; rule import/draft-from-text.
- System health; integrations catalogue; narrow applicant DTOs.
- Optional Sarvam STT; simulated issuers.

---

## 3. Partially implemented

| Area | Gap |
|------|-----|
| Category checklists | Categories share seed `DEFAULT_DOCS`; upload validates against `DEFAULT_DOCS` not category JSON |
| Clarification `finding_ids` | API accepts array; only first ID stored |
| Document replace | Versions kept; `DocumentStatus.REPLACED` unused; verif runs not marked superseded |
| Notification bell | Decorative only |
| PDF viewer | iframe blob; bbox stored but never highlighted |
| Celery/Redis | Config flags only; sync `enqueue` |
| New Application categories | Hardcoded options; not Categories API |
| Dual `run_for_application` | Called twice during validation (wasteful) |

---

## 4. Missing (deferred beyond Phase 3 unless noted)

- Production auth; in-app notification store; Celery jobs.
- Academic-year-specific requirement matrix.
- Dependency-aware partial reverify (Phase 4).
- Email/SMS; signed report attestation.
- Full three-panel case workspace (Phase 3 target).

---

## 5. Broken / inconsistent workflows

- Upload ignores per-category `required_documents` → category-only codes cannot upload.
- Deficiencies page title vs nav “Clarifications”.
- Comparison page N+1 API fetches.
- Demo mock fallback in `useApplicationDetail` can look like live data if API down (labeled, but risky).

---

## 6. Security / isolation risks

- Spoofable demo headers when `DEMO_AUTH_ENABLED=true`.
- Institution scoping is solid *given* correct identity.
- File download path-sandboxed; applicant narrow DTO is good.
- Treat demo auth as non-production forever in UI copy.

---

## 7. UI/UX problems

- Officer desk is tabbed + modal, not evidence-first workspace.
- Applicant dashboard lacks stage cards, readiness gate, unified action-required.
- Status vocabulary inconsistent across applicant vs officer labels.
- Decorative notification + inert user chevron.
- Breadcrumbs are non-link strings.
- Priority score can be misread as fraud risk without “why prioritized”.

---

## 8. Implementation order (this pass)

1. **Phase 0** — This audit (done).
2. **Phase 1** — Status vocabulary module; shell polish (workspace label, notification honesty); nav labels; PageHeader description slot. **DONE**
3. **Phase 2** — Applicant overview (stage cards, action-required); detail readiness panel; load categories from API; upload against category checklist; clarifications UX. **DONE (core)**
4. **Phase 3** — Officer case workspace layout; pdf.js viewer with bbox overlay when coords exist; finding → page navigation; “why prioritized”; structured clarification from selected findings. **PARTIAL** (PDF bbox viewer + why prioritized; full three-panel layout still uses tabs + report panel)

### Progress log (2026-10-28)

**Phase 1 shipped**

- `frontend/src/lib/statusVocabulary.ts` — centralized labels/meanings for status, verification, priority, outcomes.
- `StatusBadge` / `Badge` — tooltips from vocabulary.
- `AppShell` — optional `description` under title.
- `TopBar` — workspace chip; honest notifications dialog (no fake unread dot); removed inert chevron.
- Nav labels: Overview / Create Application / My Queue / Cross-document Comparison.

**Phase 2 shipped**

- Applicant overview: primary CTA context, action-required list, stage-oriented summary cards, empty state.
- Application detail: readiness review (must fix / review recommended / limitations).
- `GET /api/v1/applications/categories` — active categories + checklist for applicants.
- New application form loads categories from API (fallback retained).
- Upload validates requirement codes against **category** `required_documents` (fallback `DEFAULT_DOCS`).
- Clarifications page title aligned with nav.

**Phase 3 partial**

- `PdfEvidenceViewer` + `DocumentPreview` — page nav, zoom, optional bbox highlight (never invented).
- Document report field rows selectable → jump/highlight when `pageNumber`/`bbox` exist.
- Officer case header: “Why prioritized” from score contributions; page description clarifies decision-support.

**Still open for later sessions**

- Full three-panel persistent case workspace (replace tab+modal primary path).
- Finding → page highlight from Issues tab (not only document report fields).
- Multi-`finding_ids` on clarifications; stale verification supersession flags.
- Celery jobs; in-app notification store; production auth.

---

## 9. Files expected to change

**Phase 1:** `lib/statusVocabulary.ts` (new), `StatusBadge.tsx`, `AppShell.tsx`, `TopBar.tsx`, `Sidebar.tsx`, `lib/nav.ts`, `EmptyState` usage, `index.css` (minor).

**Phase 2:** Applicant pages, `DocumentUploadControl`, backend `document_service` (category checklist), optional categories list API already exists.

**Phase 3:** `ApplicationDetailPage`, `DocumentPreview`/`DocumentViewer`, Issues/Reconciliation panels, types for bbox.

**Migrations:** Only if Phase 2/3 need multi-finding clarification or superseded flags (prefer Phase 4 for full lifecycle; Phase 3 may store finding_ids as JSON without new tables if schema allows).

---

## 10. Regression risks & testing

- RBAC matrix and applicant isolation tests must stay green.
- Navigation tests (`navigation.test.tsx`).
- Extraction/verification/report/audit-chain suites.
- Frontend: `npm run typecheck` + vitest; backend: `pytest -q`.
- Manual: create app → upload → officer issues → clarification → resubmit → recommend.
- Never present simulated Layer-2 as official verification in new UI copy.

---

## Non-goals this pass

- Full rewrite / new starter template.
- Celery/Redis production queue.
- Real IdP.
- Inventing official APH rules.
- Claiming bbox highlight when coordinates are null.
