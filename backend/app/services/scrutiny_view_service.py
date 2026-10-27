"""Officer-facing scrutiny review: grouped issues, document cards, decision context.

Everything here is *read-only* and built from persisted results of the latest completed validation
run. Plain-language wording lives in ``issue_text``; handbook citations come only from the
administrator-verified registry in ``handbook_service``. The per-document pipeline lives in
``document_report_service``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.seed import DEFAULT_DOCS
from app.document_processing.ocr_processor import tesseract_status
from app.models.application import Application
from app.models.doc_verification import DocumentVerificationCheck, DocumentVerificationRun
from app.models.document import Document
from app.models.enums import ReviewDecisionType
from app.models.extraction import ExtractionRun
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.validation import Finding
from app.schemas.scrutiny import (
    DecisionContextOut,
    DeficiencyContextOut,
    DocumentCardOut,
    DocumentIssueGroupOut,
    HandbookReferenceOut,
    IssueEvidenceOut,
    MissingDocumentOut,
    RelatedDocumentOut,
    ScrutinyIssueOut,
    ScrutinyReviewOut,
)
from app.services import findings_service, issue_text
from app.services.document_check_service import build_document_check
from app.services.handbook_service import HandbookResolver

DISCLAIMER = (
    "This review supports the scrutiny officer. Passing automated rules does not prove a document "
    "is authentic, and no result here is a fraud determination. The officer makes the final decision."
)
SEVERITY_RANK = {"failed": 3, "manual_review": 2, "warning": 1, "info": 0}
COUNTED = ("failed", "manual_review", "warning")
PASS_OUTCOMES = {"pass", "verified_by_source"}


def enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def norm_severity(s: str | None) -> str:
    s = (s or "info").lower()
    return s if s in SEVERITY_RANK else "warning"


# ---- shared context -------------------------------------------------------------------


class ReviewContext:
    """Loads everything once for an application (shared with the per-document report)."""

    def __init__(self, db: Session, app: Application):
        self.db = db
        self.app = app
        self.docs = sorted(app.documents, key=lambda d: d.created_at)
        self.doc_by_id = {d.id: d for d in self.docs}
        self.handbook = HandbookResolver(db)
        self.run = findings_service.latest_completed_run(db, app.id)
        self.findings = findings_service.current_findings(db, app.id, with_evidence=True)
        self.verif_runs = self._latest_verif_runs()
        self.extraction_runs: dict[str, ExtractionRun | None] = {
            d.id: self._latest_extraction(d) for d in self.docs if d.latest_version
        }

    def _latest_verif_runs(self) -> dict[str, DocumentVerificationRun]:
        rows = (
            self.db.query(DocumentVerificationRun)
            .filter(DocumentVerificationRun.application_id == self.app.id)
            .order_by(DocumentVerificationRun.created_at.desc())
            .all()
        )
        out: dict[str, DocumentVerificationRun] = {}
        for r in rows:
            cur = self.doc_by_id.get(r.document_id)
            # Only a run on the document's *current* version describes the current file.
            if cur and cur.latest_version and r.document_version_id != cur.latest_version.id:
                continue
            out.setdefault(r.document_id, r)
        return out

    def _latest_extraction(self, doc: Document) -> ExtractionRun | None:
        v = doc.latest_version
        return (
            self.db.query(ExtractionRun)
            .filter(ExtractionRun.document_version_id == v.id)
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )

    def doc_name(self, doc_id: str | None) -> str | None:
        d = self.doc_by_id.get(doc_id) if doc_id else None
        return d.name if d else None


# ---- raw issue collection / merging ----------------------------------------------------


@dataclass
class _Raw:
    topic: str
    title: str
    explanation: str
    severity: str
    status: str
    source: str
    layer: str
    document_id: str | None
    action: str | None
    handbook: HandbookReferenceOut
    finding_ids: list[str] = field(default_factory=list)
    check_ids: list[str] = field(default_factory=list)
    evidence: list[IssueEvidenceOut] = field(default_factory=list)
    related_doc_ids: list[str] = field(default_factory=list)
    occurrences: int = 1


def _merge(raws: list[_Raw]) -> list[_Raw]:
    """Deduplicate by (document, topic): one issue per real problem, however many rules saw it."""
    merged: dict[tuple[str | None, str], _Raw] = {}
    for r in raws:
        key = (r.document_id, r.topic)
        cur = merged.get(key)
        if cur is None:
            merged[key] = r
            continue
        cur.occurrences += 1
        if SEVERITY_RANK[r.severity] > SEVERITY_RANK[cur.severity]:
            cur.severity = r.severity
            cur.title = r.title
            cur.explanation = r.explanation
        if r.status == "open":
            cur.status = "open"
        cur.finding_ids += [i for i in r.finding_ids if i not in cur.finding_ids]
        cur.check_ids += [i for i in r.check_ids if i not in cur.check_ids]
        cur.related_doc_ids += [i for i in r.related_doc_ids if i not in cur.related_doc_ids]
        seen = {e.text for e in cur.evidence}
        cur.evidence += [e for e in r.evidence if e.text not in seen]
        if cur.action is None and r.action:
            cur.action = r.action
        if cur.handbook.status != "verified" and r.handbook.status == "verified":
            cur.handbook = r.handbook
    out = list(merged.values())
    for r in out:
        r.evidence = r.evidence[:8]
    return out


def _finding_raw(ctx: ReviewContext, f: Finding) -> _Raw | None:
    code = f.rule_code or ""
    if code == "SYN-RULE-008":
        return None  # capability disclosure: shown as a limitation, not an issue
    doc_name = ctx.doc_name(f.document_id)
    text = issue_text.describe_finding(code, f.title, f.description, doc_name)
    related = [e.document_id for e in f.evidence if e.document_id and e.document_id != f.document_id]
    related = list(dict.fromkeys(related))
    return _Raw(
        topic=text.topic,
        title=text.title,
        explanation=text.explanation,
        severity=norm_severity(enum_val(f.severity)),
        status=enum_val(f.status),
        source=text.source,
        layer=text.layer,
        document_id=f.document_id,
        action=text.applicant_action,
        handbook=ctx.handbook.lookup(code),
        finding_ids=[f.id],
        evidence=[
            IssueEvidenceOut(
                text=issue_text.clean(e.description),
                document_id=e.document_id,
                document_name=e.document_name,
                page_reference=e.page_reference,
            )
            for e in f.evidence
        ],
        related_doc_ids=related,
    )


def _check_raw(
    ctx: ReviewContext, run: DocumentVerificationRun, c: DocumentVerificationCheck
) -> _Raw | None:
    layer = enum_val(c.layer)
    if layer == "layer3_review" or c.outcome in PASS_OUTCOMES:
        return None  # Layer 3 is a pipeline stage; passes are not issues
    doc = ctx.doc_by_id.get(c.document_id)
    doc_name = doc.name if doc else "this document"
    text = issue_text.describe_check(c.check_code, c.title, c.detail, doc_name, layer)
    severity = norm_severity(c.severity)
    if layer == "layer2_external":
        if c.outcome == "mismatch_detected":
            severity = "failed"
            text = issue_text.IssueText(
                title=f"Verification source reports a mismatch ({c.adapter or 'adapter'})",
                explanation=issue_text.clean(c.detail)
                or "An automated verification check found a mismatch.",
                applicant_action="Check the document details and provide a corrected copy.",
                layer="layer2",
                source="external",
                topic=f"l2:mismatch:{c.check_code}",
            )
        else:
            severity = "info"  # unavailable/simulated sources are limits, not defects
    is_l1 = layer == "layer1_rules"
    return _Raw(
        topic=text.topic,
        title=text.title,
        explanation=text.explanation,
        severity=severity,
        status=c.status if c.status in ("open", "resolved", "waived", "accepted") else "open",
        source=text.source,
        layer=text.layer,
        document_id=c.document_id,
        action=text.applicant_action,
        handbook=(
            ctx.handbook.lookup(f"{run.config_code}:{c.check_code}", run.config_code)
            if is_l1
            else ctx.handbook.lookup()
        ),
        check_ids=[c.id],
        evidence=(
            [IssueEvidenceOut(text=issue_text.clean(c.detail), document_id=c.document_id)]
            if c.detail
            else []
        ),
    )


def collect_issues(ctx: ReviewContext) -> list[ScrutinyIssueOut]:
    raws: list[_Raw] = []
    for f in ctx.findings:
        r = _finding_raw(ctx, f)
        if r:
            raws.append(r)
    for run in ctx.verif_runs.values():
        for c in run.checks:
            r = _check_raw(ctx, run, c)
            if r:
                raws.append(r)
    out: list[ScrutinyIssueOut] = []
    for r in _merge(raws):
        doc = ctx.doc_by_id.get(r.document_id) if r.document_id else None
        out.append(
            ScrutinyIssueOut(
                key=f"{r.document_id or 'app'}:{r.topic}",
                title=r.title,
                explanation=r.explanation,
                severity=r.severity,
                status=r.status,
                source=r.source,
                layer=r.layer,
                document_id=r.document_id,
                document_name=doc.name if doc else None,
                requirement_code=doc.requirement_code if doc else None,
                related_documents=[
                    RelatedDocumentOut(id=i, name=ctx.doc_name(i) or i) for i in r.related_doc_ids
                ],
                applicant_action=r.action,
                handbook=r.handbook,
                finding_ids=r.finding_ids,
                check_ids=r.check_ids,
                occurrences=r.occurrences,
                evidence=r.evidence,
            )
        )
    out.sort(key=lambda i: (-SEVERITY_RANK[i.severity], i.status != "open", i.title))
    return out


def group_issues(ctx: ReviewContext, issues: list[ScrutinyIssueOut]) -> list[DocumentIssueGroupOut]:
    groups: list[DocumentIssueGroupOut] = []

    def make(doc_id, name, code, scope, items):
        counted_open = [i for i in items if i.status == "open" and i.severity in COUNTED]
        highest = max(
            (i.severity for i in counted_open), key=lambda s: SEVERITY_RANK[s], default=None
        )
        groups.append(
            DocumentIssueGroupOut(
                document_id=doc_id,
                document_name=name,
                requirement_code=code,
                scope=scope,
                issues=items,
                open_count=len(counted_open),
                highest_severity=highest,
            )
        )

    app_level = [i for i in issues if i.document_id is None and i.layer != "cross_document"]
    cross = [i for i in issues if i.document_id is None and i.layer == "cross_document"]
    if app_level:
        make(None, "Application-level (missing or duplicated documents)", None, "application", app_level)
    if cross:
        make(None, "Across documents (values that differ)", None, "cross_document", cross)
    for d in ctx.docs:
        items = [i for i in issues if i.document_id == d.id]
        if items:
            make(d.id, d.name, d.requirement_code, "document", items)
    groups.sort(
        key=lambda g: (-SEVERITY_RANK.get(g.highest_severity or "info", 0), -g.open_count)
    )
    return groups


# ---- cards -----------------------------------------------------------------------------


def document_card(ctx: ReviewContext, doc: Document, issues: list[ScrutinyIssueOut]) -> DocumentCardOut:
    v = doc.latest_version
    run = ctx.extraction_runs.get(doc.id)
    check = build_document_check(
        requirement_name=doc.name, run=run, file_checks=(v.file_checks if v else None)
    )
    mine = [
        i for i in issues if i.document_id == doc.id and i.status == "open" and i.severity in COUNTED
    ]
    highest = max((i.severity for i in mine), key=lambda s: SEVERITY_RANK[s], default=None)
    return DocumentCardOut(
        id=doc.id,
        name=doc.name,
        requirement_code=doc.requirement_code,
        file_name=v.file_name if v else doc.name,
        version=doc.current_version,
        mime_type=v.mime_type if v else "application/octet-stream",
        size_bytes=v.size_bytes if v else 0,
        uploaded_at=v.uploaded_at if v else doc.created_at,
        page_count=v.page_count if v else None,
        rule_validation_status=enum_val(doc.rule_validation_status),
        external_verification_status=enum_val(doc.external_verification_status),
        review_status=enum_val(doc.review_status),
        document_check=check,
        open_issue_count=len(mine),
        highest_severity=highest,
        can_preview=bool(v),
    )


# ---- decision context --------------------------------------------------------------------


def _decision_context(ctx: ReviewContext, issues: list[ScrutinyIssueOut]) -> DecisionContextOut:
    db, app = ctx.db, ctx.app
    notices = (
        db.query(DeficiencyNotice)
        .filter(DeficiencyNotice.application_id == app.id)
        .order_by(DeficiencyNotice.created_at.desc())
        .all()
    )
    final = (
        db.query(ReviewDecision)
        .filter(
            ReviewDecision.application_id == app.id,
            ReviewDecision.decision_type.in_(
                [ReviewDecisionType.RECOMMEND, ReviewDecisionType.REJECT, ReviewDecisionType.APPROVE]
            ),
        )
        .order_by(ReviewDecision.created_at.desc())
        .first()
    )
    must: list[str] = []
    rows: list[dict] = []
    for i in issues:
        if i.status != "open" or i.severity not in COUNTED or not i.applicant_action:
            continue
        who = f"{i.document_name}: " if i.document_name else ""
        line = f"{who}{i.applicant_action}"
        if line not in must:
            must.append(line)
            rows.append(
                {
                    "documentName": i.document_name or "Application",
                    "action": i.applicant_action,
                }
            )

    draft_title = ""
    draft_body = ""
    rejection = ""
    if must:
        draft_title = f"Corrections needed for {app.application_number}"
        draft_body = "Please correct the following and resubmit:\n" + "\n".join(
            f"{n}. {m}" for n, m in enumerate(must, 1)
        )
        rejection = (
            "The application cannot be recommended because of unresolved issues. "
            "See the correction list."
        )
    return DecisionContextOut(
        status=enum_val(app.status),
        clarification_requests=[
            DeficiencyContextOut(
                id=n.id,
                title=n.title,
                description=n.description,
                status=enum_val(n.status),
                applicant_response=n.applicant_response,
                created_at=n.created_at,
                responded_at=n.responded_at,
            )
            for n in notices
        ],
        final_decision=(
            ("recommended" if enum_val(final.decision_type) in ("recommend", "approve") else "rejected")
            if final
            else None
        ),
        final_decision_reason=final.content if final else None,
        final_decision_by=(final.author.name if final and final.author else None),
        final_decision_at=final.created_at.isoformat() if final else None,
        must_correct=must,
        must_correct_rows=rows,
        clarification_draft_title=draft_title,
        clarification_draft_body=draft_body,
        rejection_draft_body=rejection,
    )


def _limitations(ctx: ReviewContext) -> list[str]:
    out: list[str] = []
    for f in ctx.findings:
        if f.rule_code == "SYN-RULE-008":
            out.append(issue_text.clean(f.description))
    for run in ctx.verif_runs.values():
        for lim in run.limitations or []:
            if lim and lim not in out:
                out.append(lim)
    ocr = tesseract_status()
    if not ocr.get("available"):
        out.append(
            "OCR (Tesseract) is not installed on this server: scanned pages could not be read "
            "automatically."
        )
    elif "mar" in get_settings().ocr_language_list and not ocr.get("marathi_supported"):
        out.append("Marathi OCR data is not installed: Marathi scans may not be read correctly.")
    return out[:12]


def build_review(db: Session, app: Application) -> ScrutinyReviewOut:
    ctx = ReviewContext(db, app)
    issues = collect_issues(ctx)
    groups = group_issues(ctx, issues)
    reqs = app.category.required_documents if app.category else DEFAULT_DOCS
    uploaded = {d.requirement_code for d in ctx.docs}
    missing = [
        MissingDocumentOut(code=r["code"], name=r["name"], mandatory=bool(r.get("mandatory", True)))
        for r in reqs
        if r["code"] not in uploaded
    ]
    counted = [i for i in issues if i.severity in COUNTED]
    return ScrutinyReviewOut(
        application_id=app.id,
        application_number=app.application_number,
        institution_name=app.institution_name or (app.institution.name if app.institution else ""),
        status=enum_val(app.status),
        generated_at=datetime.now(timezone.utc),
        validation_run_id=ctx.run.id if ctx.run else None,
        validation_completed_at=ctx.run.completed_at if ctx.run else None,
        documents=[document_card(ctx, d, issues) for d in ctx.docs],
        missing_documents=missing,
        issue_groups=groups,
        open_issue_count=sum(1 for i in counted if i.status == "open"),
        resolved_issue_count=sum(1 for i in counted if i.status != "open"),
        historical_finding_count=findings_service.historical_finding_count(db, app.id),
        limitations=_limitations(ctx),
        decision=_decision_context(ctx, issues),
        disclaimer=DISCLAIMER,
    )

def open_issue_count(db: Session, app: Application) -> int:
    """Open issues exactly as the scrutiny review counts them (grouped, de-duplicated, current
    run only), so queue/dashboard numbers cannot disagree with the review screen."""
    ctx = ReviewContext(db, app)
    return sum(1 for i in collect_issues(ctx) if i.severity in COUNTED and i.status == "open")
