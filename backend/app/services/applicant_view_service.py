"""Applicant-facing application view.

Deliberately narrow: applications, required documents, upload status, clarifications
(deficiencies) and history. It never includes extracted fields, internal priority scores,
forensic indicators, rule codes, verification run codes or officer notes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFoundError
from app.core.security import ensure_application_access
from app.core.seed import DEFAULT_DOCS
from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.enums import ApplicationStatus, DeficiencyStatus, UserRole
from app.models.review import DeficiencyNotice
from app.models.user import User
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


def _counts(rows: list[ApplicantRequirementOut]) -> tuple[int, int]:
    mandatory = [r for r in rows if r.mandatory]
    return len(mandatory), sum(1 for r in mandatory if r.document is not None)


def get_applicant_application(db: Session, user: User, application_id: str) -> ApplicantApplicationOut:
    app = _load_app(db, user, application_id)
    status = app.status.value if hasattr(app.status, "value") else str(app.status)
    rows = _requirement_rows(db, app)
    total, uploaded = _counts(rows)
    blockers = resubmit_blockers(db, app)
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
        deficiencies=_deficiency_rows(db, app),
        history=_history_rows(db, app),
        can_upload=app.status not in TERMINAL_STATUSES,
        can_resubmit=can_resubmit,
        resubmit_blockers=blockers if app.status in (
            ApplicationStatus.CLARIFICATION_REQUIRED,
            ApplicationStatus.DEFICIENCY,
        ) else [],
        required_total=total,
        required_uploaded=uploaded,
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
        open_count = (
            db.query(DeficiencyNotice)
            .filter(
                DeficiencyNotice.application_id == app.id,
                DeficiencyNotice.status == DeficiencyStatus.OPEN,
            )
            .count()
        )
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
            )
        )
    return out
