"""Applicant-facing application view.

Deliberately narrow: applications, required documents, upload status, clarifications
(deficiencies), final decisions, and officer resolution notes the applicant should see.
It never includes extracted fields, internal priority scores, forensic indicators,
rule codes or verification run codes.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFoundError
from app.core.security import ensure_application_access
from app.core.seed import DEFAULT_DOCS
from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.doc_verification import DocumentVerificationCheck
from app.models.enums import ApplicationStatus, DeficiencyStatus, ReviewDecisionType, UserRole
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.user import User
from app.services import findings_service
from app.schemas.common import (
    ApplicantApplicationOut,
    ApplicantApplicationSummaryOut,
    ApplicantDeficiencyOut,
    ApplicantDocumentOut,
    ApplicantDocumentVersionOut,
    ApplicantHistoryEntryOut,
    ApplicantRequirementOut,
)
from app.services.serializers import document_to_out
from app.services.workflow_service import resubmit_blockers

STATUS_LABELS: dict[str, tuple[str, str]] = {
    "draft": ("Draft", "This application has not been submitted yet."),
    "submitted": ("Submitted", "Your application was received. Upload the required documents."),
    "processing": ("Being checked", "Your documents are being checked automatically."),
    "under_scrutiny": (
        "Under review",
        "A scrutiny officer is reviewing your application. No action is needed unless they contact you.",
    ),
    "clarification_required": (
        "Action needed",
        "The scrutiny officer needs clarification. Respond to each request below, "
        "replace any documents that need correcting, then resubmit.",
    ),
    "resubmitted": ("Resubmitted", "Your response was received and is waiting for officer review."),
    "recommended": (
        "Recommended",
        "The scrutiny officer has recommended this application for the next stage.",
    ),
    "rejected": ("Rejected", "The scrutiny officer has rejected this application. See the reason below."),
    # Legacy statuses still present in older demo rows
    "awaiting_review": ("Under review", "Your application is waiting for officer review."),
    "under_review": ("Under review", "A scrutiny officer is reviewing your application."),
    "deficiency": (
        "Action needed",
        "The scrutiny officer needs clarification. Respond to each request below, then resubmit.",
    ),
    "manual_review": ("Under review", "A scrutiny officer is reviewing your application."),
    "approved": ("Recommended", "The scrutiny officer has recommended this application."),
}

TERMINAL_STATUSES = {
    ApplicationStatus.RECOMMENDED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.APPROVED,
}

# audit action -> applicant-readable label. Anything not listed is internal and never shown.
_HISTORY_LABELS: dict[str, str] = {
    "application.created": "Application created",
    "document.uploaded": "Document uploaded",
    "workflow.under_scrutiny": "Automatic checks completed — under review",
    "workflow.start_scrutiny": "Officer started the review",
    "workflow.clarification_requested": "Clarification requested",
    "workflow.deficiency_responded": "You responded to a clarification request",
    "workflow.resubmitted": "Application resubmitted",
    "workflow.recommended": "Recommended by the scrutiny officer",
    "workflow.rejected": "Rejected by the scrutiny officer",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, (status.replace("_", " ").title(), ""))[0]


def _status_message(status: str) -> str:
    return STATUS_LABELS.get(status, ("", ""))[1]


def _history_detail(action: str, detail: str) -> str | None:
    detail = (detail or "").strip()
    if action in ("workflow.recommended", "workflow.rejected", "workflow.clarification_requested"):
        # transition audit detail looks like "prev → new; reason"; show the reason only
        _, _, reason = detail.partition("; ")
        return reason.strip() or None
    if action in ("document.uploaded", "application.created"):
        return detail or None
    if action == "workflow.resubmitted":
        _, _, note = detail.partition("; ")
        return note.strip() or None
    return None


def _required_defs(app: Application) -> list[dict]:
    return list(app.category.required_documents if app.category else DEFAULT_DOCS)


def _load_app(db: Session, user: User, application_id: str) -> Application:
    if user.role != UserRole.APPLICANT:
        # Officers/admins use the scrutiny/admin views, not the applicant view.
        raise NotFoundError("Application not found")
    app = (
        db.query(Application)
        .options(
            joinedload(Application.institution),
            joinedload(Application.category),
            joinedload(Application.documents),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    return app


def _requirement_rows(db: Session, app: Application) -> list[ApplicantRequirementOut]:
    docs_by_code = {d.requirement_code: d for d in app.documents}
    rows: list[ApplicantRequirementOut] = []
    for r in _required_defs(app):
        doc = docs_by_code.get(r["code"])
        document = None
        if doc is None:
            upload_status, label = "not_uploaded", "Not uploaded"
        else:
            doc_out = document_to_out(doc, db)
            check = doc_out.document_check
            previous = [
                ApplicantDocumentVersionOut(
                    version=v.version,
                    file_name=v.file_name,
                    uploaded_at=v.uploaded_at,
                    size_bytes=v.size_bytes,
                )
                for v in sorted(doc.versions, key=lambda x: x.version, reverse=True)
                if v.version != doc.current_version
            ]
            document = ApplicantDocumentOut(
                id=doc.id,
                file_name=doc_out.file_name,
                version=doc_out.version,
                uploaded_at=doc_out.uploaded_at,
                size_bytes=doc_out.size_bytes,
                document_check=check,
                previous_versions=previous,
            )
            if check and check.needs_attention:
                upload_status, label = "needs_attention", "Uploaded — please check"
            elif doc.current_version > 1:
                upload_status, label = "replaced", f"Replaced (version {doc.current_version})"
            else:
                upload_status, label = "uploaded", "Uploaded"
        rows.append(
            ApplicantRequirementOut(
                code=r["code"],
                name=r["name"],
                mandatory=bool(r.get("mandatory", True)),
                allowed_types=list(r.get("allowed_types") or ["pdf"]),
                upload_status=upload_status,
                upload_status_label=label,
                document=document,
            )
        )
    return rows


def _deficiency_rows(db: Session, app: Application) -> list[ApplicantDeficiencyOut]:
    notices = (
        db.query(DeficiencyNotice)
        .filter(DeficiencyNotice.application_id == app.id)
        .order_by(DeficiencyNotice.created_at.desc())
        .all()
    )
    order = {DeficiencyStatus.OPEN: 0, DeficiencyStatus.RESPONDED: 1, DeficiencyStatus.CLOSED: 2}
    notices.sort(key=lambda n: order.get(n.status, 3))
    return [
        ApplicantDeficiencyOut(
            id=n.id,
            title=n.title,
            description=n.description,
            status=n.status.value if hasattr(n.status, "value") else str(n.status),
            applicant_response=n.applicant_response,
            responded_at=n.responded_at,
            created_at=n.created_at,
            resolved_at=n.resolved_at,
        )
        for n in notices
    ]


def _history_rows(db: Session, app: Application) -> list[ApplicantHistoryEntryOut]:
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.application_id == app.id, AuditEvent.action.in_(list(_HISTORY_LABELS)))
        .order_by(AuditEvent.created_at.desc())
        .all()
    )
    return [
        ApplicantHistoryEntryOut(
            id=e.id,
            timestamp=e.created_at,
            label=_HISTORY_LABELS[e.action],
            detail=_history_detail(e.action, e.detail),
        )
        for e in events
    ]


def _latest_decision(db: Session, app: Application) -> ReviewDecision | None:
    return (
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


def _decision_label(row: ReviewDecision | None) -> str | None:
    if row is None:
        return None
    kind = row.decision_type.value if hasattr(row.decision_type, "value") else str(row.decision_type)
    if kind in ("recommend", "approve"):
        return "recommended"
    if kind == "reject":
        return "rejected"
    return kind


def _short_reason(text: str | None) -> str | None:
    if not text:
        return None
    first = text.strip().split("\n", 1)[0].strip()
    if first.startswith("The application cannot be recommended"):
        return "The officer recorded a decision. The items to correct are listed below."
    return first[:280]


def _correction_rows(notices: list[ApplicantDeficiencyOut], decision: ReviewDecision | None) -> list[dict]:
    rows: list[dict] = []
    for n in notices:
        if n.status not in ("open", "responded"):
            continue
        rows.append({"documentName": n.title, "action": n.description, "status": n.status})
    if not rows and decision and decision.content:
        parts = re.split(r"\n+|(?:;\s*(?=[A-Z][^:]{2,70}:\s))", decision.content)
        for raw in parts:
            line = raw.strip(" -–\t")
            if not line or line.startswith("The application cannot"):
                continue
            if line[:2].rstrip(".").isdigit() or (len(line) > 2 and line[0].isdigit() and line[1] == "."):
                line = line.split(".", 1)[-1].strip()
            if ": " in line[:80]:
                doc, action = line.split(": ", 1)
                rows.append({"documentName": doc.strip(), "action": action.strip(), "status": "from_decision"})
            elif line:
                rows.append({"documentName": "Application", "action": line, "status": "from_decision"})
    return rows


_STATUS_PLAIN = {
    "resolved": "Resolved — no further action needed on this item",
    "waived": "Waived — the officer is not requiring a correction for this stage",
    "accepted": "Accepted — the officer accepted the finding as recorded",
}


def _doc_label(app: Application, document_id: str | None) -> str:
    if not document_id:
        return "Application"
    docs = {d.id: d for d in app.documents}
    doc = docs.get(document_id)
    if doc is None:
        return "Document"
    names = {r["code"]: r["name"] for r in _required_defs(app)}
    return names.get(doc.requirement_code) or doc.file_name or doc.requirement_code


def _officer_updates(db: Session, app: Application) -> list[dict]:
    """Closed findings/checks with an officer note, safe for the applicant to read."""
    rows: list[dict] = []
    for finding in findings_service.current_findings(db, app.id):
        status = finding.status.value if hasattr(finding.status, "value") else str(finding.status)
        if status not in ("resolved", "waived", "accepted"):
            continue
        note = (finding.resolution_reason or "").strip()
        if len(note) < 5:
            continue
        rows.append(
            {
                "documentName": _doc_label(app, finding.document_id),
                "issue": finding.title,
                "status": status,
                "statusLabel": _STATUS_PLAIN.get(status, status),
                "note": note,
            }
        )
    checks = (
        db.query(DocumentVerificationCheck)
        .filter(
            DocumentVerificationCheck.application_id == app.id,
            DocumentVerificationCheck.status.in_(["resolved", "waived", "accepted"]),
        )
        .order_by(DocumentVerificationCheck.resolved_at.desc())
        .limit(40)
        .all()
    )
    for check in checks:
        note = (check.resolution_reason or "").strip()
        if len(note) < 5:
            continue
        rows.append(
            {
                "documentName": _doc_label(app, check.document_id),
                "issue": check.title,
                "status": check.status,
                "statusLabel": _STATUS_PLAIN.get(check.status, check.status),
                "note": note,
            }
        )
    return rows[:30]


def _counts(rows: list[ApplicantRequirementOut]) -> tuple[int, int]:
    mandatory = [r for r in rows if r.mandatory]
    return len(mandatory), sum(1 for r in mandatory if r.document is not None)


def get_applicant_application(db: Session, user: User, application_id: str) -> ApplicantApplicationOut:
    app = _load_app(db, user, application_id)
    status = app.status.value if hasattr(app.status, "value") else str(app.status)
    rows = _requirement_rows(db, app)
    total, uploaded = _counts(rows)
    blockers = resubmit_blockers(db, app)
    decision = _latest_decision(db, app)
    notices = _deficiency_rows(db, app)
    can_resubmit = app.status in (
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.DEFICIENCY,
    ) and not blockers
    return ApplicantApplicationOut(
        id=app.id,
        application_number=app.application_number,
        institution_name=app.institution_name or (app.institution.name if app.institution else ""),
        category=app.category.name if app.category else "",
        category_code=app.category.code if app.category else "",
        program_name=app.program_name,
        academic_year=app.academic_year,
        status=status,
        status_label=status_label(status),
        status_message=_status_message(status),
        submitted_at=app.submitted_at,
        requirements=rows,
        deficiencies=notices,
        history=_history_rows(db, app),
        can_upload=app.status not in TERMINAL_STATUSES,
        can_resubmit=can_resubmit,
        resubmit_blockers=blockers if app.status in (
            ApplicationStatus.CLARIFICATION_REQUIRED,
            ApplicationStatus.DEFICIENCY,
        ) else [],
        required_total=total,
        required_uploaded=uploaded,
        officer_decision=_decision_label(decision),
        officer_decision_reason=_short_reason(decision.content if decision else None),
        officer_decision_at=decision.created_at if decision else None,
        corrections=_correction_rows(notices, decision),
        officer_updates=_officer_updates(db, app),
    )


def list_applicant_applications(db: Session, user: User) -> list[ApplicantApplicationSummaryOut]:
    if user.role != UserRole.APPLICANT or not user.institution_id:
        return []
    apps = (
        db.query(Application)
        .options(
            joinedload(Application.institution),
            joinedload(Application.category),
            joinedload(Application.documents),
        )
        .filter(Application.institution_id == user.institution_id)
        .order_by(Application.created_at.desc())
        .all()
    )
    out: list[ApplicantApplicationSummaryOut] = []
    for app in apps:
        status = app.status.value if hasattr(app.status, "value") else str(app.status)
        defs = [r for r in _required_defs(app) if r.get("mandatory", True)]
        uploaded_codes = {d.requirement_code for d in app.documents}
        open_q = (
            db.query(DeficiencyNotice)
            .filter(
                DeficiencyNotice.application_id == app.id,
                DeficiencyNotice.status == DeficiencyStatus.OPEN,
            )
            .order_by(DeficiencyNotice.created_at.desc())
        )
        open_count = open_q.count()
        latest_open = open_q.first()
        decision = _latest_decision(db, app)
        out.append(
            ApplicantApplicationSummaryOut(
                id=app.id,
                application_number=app.application_number,
                institution_name=app.institution_name
                or (app.institution.name if app.institution else ""),
                category=app.category.name if app.category else "",
                program_name=app.program_name,
                academic_year=app.academic_year,
                status=status,
                status_label=status_label(status),
                submitted_at=app.submitted_at,
                open_clarifications=open_count,
                required_total=len(defs),
                required_uploaded=sum(1 for r in defs if r["code"] in uploaded_codes),
                officer_decision=_decision_label(decision),
                latest_request_title=(
                    latest_open.title
                    if latest_open
                    else _short_reason(decision.content if decision else None)
                ),
            )
        )
    return out
