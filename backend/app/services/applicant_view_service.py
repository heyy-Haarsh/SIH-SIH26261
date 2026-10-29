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
from app.models.finding_transition import DeficiencyFinding
from app.models.validation import Finding
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.user import User
from app.services import applicant_findings_service, applicant_lifecycle, findings_service
from app.models.document import ExtractedField
from app.models.enums import RuleValidationStatus
from app.schemas.common import (
    ApplicantActivityOut,
    ApplicantCheckOut,
    ApplicantEvidenceFieldOut,
    ApplicantEvidenceOut,
    ApplicantNextActionOut,
    ApplicantOverviewOut,
    ApplicantApplicationOut,
    ApplicantApplicationSummaryOut,
    ApplicantDeficiencyOut,
    ApplicantLinkedItemOut,
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
    "application.submitted": "Application submitted",
    "workflow.processing_started": "Automatic checks started",
    "validation.run_completed": "Automatic checks completed",
}


_SYSTEM_ACTIONS = {"workflow.processing_started", "workflow.under_scrutiny", "validation.run_completed"}


def _source_of(role: str | None, action: str = "") -> str:
    """Who did it, in the institution's terms: you / the officer / the system."""
    if action in _SYSTEM_ACTIONS:
        return "system"  # recorded under a person's name, but not done by them
    if role in ("officer", "regional_officer"):
        return "officer"
    if role == "applicant":
        return "you"
    return "system"


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
    from app.services import category_config_service

    return category_config_service.effective_requirements(app)


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


def _document_out(db: Session, doc) -> ApplicantDocumentOut:
    """Applicant view of one document slot: every version, with that version's own processing state."""
    doc_out = document_to_out(doc, db)
    runs = applicant_findings_service.latest_runs_by_version(db, doc)
    findings_by_version: dict[int, int] = {}
    for f in db.query(Finding).filter(Finding.document_id == doc.id):
        v = applicant_findings_service._finding_version(db, f, doc)
        if v is not None:
            findings_by_version[v] = findings_by_version.get(v, 0) + 1

    def entry(v) -> ApplicantDocumentVersionOut:
        state, message = applicant_findings_service.processing_info(runs.get(v.version))
        return ApplicantDocumentVersionOut(
            version=v.version,
            file_name=v.file_name,
            uploaded_at=v.uploaded_at,
            size_bytes=v.size_bytes,
            is_current=v.version == doc.current_version,
            processing_state=state,
            processing_message=message,
            officer_items=findings_by_version.get(v.version, 0),
        )

    versions = [entry(v) for v in sorted(doc.versions, key=lambda x: x.version, reverse=True)]
    current = next((v for v in versions if v.is_current), None)
    pending = doc.current_version > 1 and (
        doc.rule_validation_status == RuleValidationStatus.PENDING
        or current is None
        or current.processing_state in ("processing", "not_run")
    )
    latest = doc.latest_version
    return ApplicantDocumentOut(
        id=doc.id,
        file_name=doc_out.file_name,
        version=doc_out.version,
        uploaded_at=doc_out.uploaded_at,
        size_bytes=doc_out.size_bytes,
        mime_type=latest.mime_type if latest else "",
        page_count=latest.page_count if latest else None,
        document_check=doc_out.document_check,
        previous_versions=[v for v in versions if not v.is_current],
        versions=versions,
        processing_state=current.processing_state if current else "not_run",
        processing_message=current.processing_message if current else "",
        reverification_pending=bool(pending),
    )


def _check_rows(req: dict, results: list) -> list[ApplicantCheckOut]:
    """Configured checks for a requirement with their latest result. Technical limits are not failures."""
    from app.services import category_config_service as _ccs

    by_rule = {x.rule_id: x for x in results}
    out: list[ApplicantCheckOut] = []
    for rule in req.get("rules") or []:
        res = by_rule.get(rule["rule_id"])
        state = res.state if res else "pending"
        out.append(
            ApplicantCheckOut(
                title=rule["title"],
                meaning=rd_explain(rule["definition"], req["name"]),
                state=state,
                state_label=_ccs.check_state_label(state),
                message=res.message if res else "",
                document_version=res.document_version if res else None,
                rule_version=rule["rule_version"],
                config_version=res.config_version if res else None,
            )
        )
    return out


def rd_explain(definition: dict, document_name: str) -> str:
    from app.rules import definition as rd

    return rd.explain(definition, document_name=document_name)["condition"]


def _requirement_rows(db: Session, app: Application) -> list[ApplicantRequirementOut]:
    docs_by_code = {d.requirement_code: d for d in app.documents}
    rows: list[ApplicantRequirementOut] = []
    from app.services import category_config_service as _ccs

    results_by_code: dict[str, list] = {}
    for res in _ccs.results_for_application(db, app.id):
        results_by_code.setdefault(res.requirement_code, []).append(res)
    for r in _required_defs(app):
        doc = docs_by_code.get(r["code"])
        document = None
        if doc is None:
            upload_status, label = "not_uploaded", "Not uploaded"
        else:
            document = _document_out(db, doc)
            check = document.document_check
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
                description=r.get("description") or "",
                max_size_mb=r.get("max_size_mb"),
                checks=_check_rows(r, results_by_code.get(r["code"], [])),
            )
        )
    return rows


def _notices(db: Session, app: Application) -> list[DeficiencyNotice]:
    notices = (
        db.query(DeficiencyNotice)
        .filter(DeficiencyNotice.application_id == app.id)
        .order_by(DeficiencyNotice.created_at.desc())
        .all()
    )
    order = {DeficiencyStatus.OPEN: 0, DeficiencyStatus.RESPONDED: 1, DeficiencyStatus.CLOSED: 2}
    notices.sort(key=lambda n: order.get(n.status, 3))
    return notices


def _deficiency_rows(db: Session, app: Application) -> list[ApplicantDeficiencyOut]:
    return applicant_findings_service.build_clarifications(db, app, _notices(db, app))

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
            source=_source_of(getattr(e, "actor_role", None), e.action),
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


def _other_documents(db: Session, app: Application) -> list[ApplicantDocumentOut]:
    """Uploads for requirements the current category no longer lists. Kept so nothing is silently lost."""
    wanted = {r["code"] for r in _required_defs(app)}
    return [_document_out(db, d) for d in app.documents if d.requirement_code not in wanted]


def _ccs_view(app: Application) -> dict:
    from app.services import category_config_service as _ccs

    return _ccs.application_config_view(app)


def _info_problems(app: Application) -> dict[str, str]:
    from app.services import category_config_service as _ccs

    return _ccs.validate_info_values(_ccs.effective_info_fields(app), app.info_values or {})


def get_applicant_application(db: Session, user: User, application_id: str) -> ApplicantApplicationOut:
    app = _load_app(db, user, application_id)
    status = applicant_lifecycle.status_value(app)
    stage = applicant_lifecycle.stage_of(status)
    rows = _requirement_rows(db, app)
    total, uploaded = _counts(rows)
    blockers = resubmit_blockers(db, app)
    decision = _latest_decision(db, app)
    notice_rows = _notices(db, app)
    notices = applicant_findings_service.build_clarifications(db, app, notice_rows)
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
        stage=stage,
        stage_label=applicant_lifecycle.stage_label(stage),
        lifecycle=applicant_lifecycle.lifecycle_steps(db, app),
        findings=applicant_findings_service.build_findings(db, app, notice_rows),
        other_documents=_other_documents(db, app),
        updated_at=app.updated_at if hasattr(app, "updated_at") else None,
        contact_email=getattr(app, "contact_email", None),
        info_fields=_ccs_view(app)["infoFields"],
        info_problems=_info_problems(app),
        config_version=_ccs_view(app)["configVersion"],
        config_available=_ccs_view(app)["configAvailable"],
    )


def _summary_next_action(
    app: Application, status: str, missing: list[dict], open_notice: DeficiencyNotice | None
) -> ApplicantNextActionOut | None:
    """The single most useful thing the institution can do on this application, or None."""
    base = dict(application_id=app.id, application_number=app.application_number)
    if status == "draft":
        if missing:
            return ApplicantNextActionOut(
                kind="continue_draft",
                title=f"Upload {len(missing)} mandatory document{'s' if len(missing) != 1 else ''}",
                reason="This draft cannot be submitted until every mandatory document is uploaded.",
                document_code=missing[0]["code"],
                **base,
            )
        return ApplicantNextActionOut(
            kind="submit_draft",
            title="Review and submit your application",
            reason="All mandatory documents are uploaded. Nothing reaches an officer until you submit.",
            **base,
        )
    if open_notice is not None:
        return ApplicantNextActionOut(
            kind="respond_clarification",
            title=open_notice.title,
            reason=(
                "The scrutiny officer needs a replacement document and a response."
                if open_notice.requires_replacement
                else "The scrutiny officer needs your response before this case can move forward."
            ),
            clarification_id=open_notice.id,
            **base,
        )
    if missing and status not in ("recommended", "rejected", "approved"):
        return ApplicantNextActionOut(
            kind="upload_documents",
            title=f"{len(missing)} mandatory document{'s' if len(missing) != 1 else ''} not uploaded",
            reason="The category checklist lists these as mandatory.",
            document_code=missing[0]["code"],
            **base,
        )
    return None


_NEXT_ORDER = {"respond_clarification": 0, "submit_draft": 1, "continue_draft": 2, "upload_documents": 3, "fix_document": 4}


def _institution_apps(db: Session, user: User) -> list[Application]:
    if user.role != UserRole.APPLICANT or not user.institution_id:
        return []
    return (
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


def _summaries(db: Session, apps: list[Application]) -> list[ApplicantApplicationSummaryOut]:
    out: list[ApplicantApplicationSummaryOut] = []
    for app in apps:
        status = applicant_lifecycle.status_value(app)
        stage = applicant_lifecycle.stage_of(status)
        defs = [r for r in _required_defs(app) if r.get("mandatory", True)]
        uploaded_codes = {d.requirement_code for d in app.documents}
        missing = [r for r in defs if r["code"] not in uploaded_codes]
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
                category_code=app.category.code if app.category else "",
                program_name=app.program_name,
                academic_year=app.academic_year,
                status=status,
                status_label=status_label(status),
                stage=stage,
                stage_label=applicant_lifecycle.stage_label(stage),
                updated_at=getattr(app, "updated_at", None) or app.created_at,
                submitted_at=app.submitted_at,
                open_clarifications=open_count,
                required_total=len(defs),
                required_uploaded=len(defs) - len(missing),
                officer_decision=_decision_label(decision),
                latest_request_title=(
                    latest_open.title
                    if latest_open
                    else _short_reason(decision.content if decision else None)
                ),
                next_action=_summary_next_action(app, status, missing, latest_open),
            )
        )
    return out


def list_applicant_applications(db: Session, user: User) -> list[ApplicantApplicationSummaryOut]:
    return _summaries(db, _institution_apps(db, user))


_ACTIVITY_ACTIONS = {**_HISTORY_LABELS}


def applicant_overview(db: Session, user: User) -> ApplicantOverviewOut:
    """Dashboard numbers with exactly one definition each.

    * active            – submitted, processing, scrutiny, applicant action, resubmitted (not drafts, not decided)
    * action_required   – applications with at least one OPEN clarification the institution can answer
    * under_scrutiny    – in officer review: scrutiny or resubmitted
    * decision_recorded – the officer recorded a recommendation or rejection (not an official approval)
    * drafts            – saved but not submitted
    """
    apps = _institution_apps(db, user)
    summaries = _summaries(db, apps)
    stages = [s.stage for s in summaries]
    actions = [s.next_action for s in summaries if s.next_action is not None]
    actions.sort(key=lambda a: _NEXT_ORDER.get(a.kind, 9))

    by_id = {a.id: a for a in apps}
    events = []
    if by_id:
        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.application_id.in_(list(by_id)),
                AuditEvent.action.in_(list(_ACTIVITY_ACTIONS)),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(30)
            .all()
        )
    activity = [
        ApplicantActivityOut(
            id=e.id,
            source=_source_of(e.actor_role, e.action),
            label=_HISTORY_LABELS[e.action],
            detail=_history_detail(e.action, e.detail),
            application_id=e.application_id,
            application_number=by_id[e.application_id].application_number,
            timestamp=e.created_at,
        )
        for e in events
        if e.application_id in by_id
    ]
    return ApplicantOverviewOut(
        active=sum(1 for s in stages if s in applicant_lifecycle.ACTIVE_STAGES),
        action_required=sum(1 for s in summaries if s.open_clarifications > 0),
        under_scrutiny=sum(1 for s in stages if s in applicant_lifecycle.SCRUTINY_STAGES),
        decision_recorded=sum(1 for s in stages if s == "decision_recorded"),
        drafts=sum(1 for s in stages if s == "draft"),
        next_actions=actions[:5],
        recent_activity=activity[:12],
    )


def list_clarifications(db: Session, user: User) -> list[ApplicantDeficiencyOut]:
    """Every clarification request across the institution's applications (the inbox)."""
    out: list[ApplicantDeficiencyOut] = []
    for app in _institution_apps(db, user):
        notices = _notices(db, app)
        if app.status == ApplicationStatus.DRAFT or not notices:
            continue
        out.extend(applicant_findings_service.build_clarifications(db, app, notices))
    order = {"action_required": 0, "response_saved": 1, "awaiting_review": 2, "resolved": 3}
    out.sort(key=lambda c: (order.get(c.applicant_state, 4), -c.created_at.timestamp()))
    return out


_PAGE = re.compile(r"(\d{1,4})")


def finding_evidence(db: Session, user: User, finding_id: str) -> ApplicantEvidenceOut:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise NotFoundError("Finding not found")
    app = _load_app(db, user, finding.application_id)  # ownership check
    if not applicant_findings_service.finding_visible_to_applicant(db, app, finding):
        raise NotFoundError("Finding not found")  # never reveal that an internal finding exists

    notices = _notices(db, app)
    built = {f.id: f for f in applicant_findings_service.build_findings(db, app, notices)}
    item = built.get(finding.id)
    if item is None:  # a superseded sibling: describe it through its current counterpart
        same = [f for f in built.values() if f.document.document_id == finding.document_id]
        item = same[0] if same else None
    if item is None:
        raise NotFoundError("Finding not found")

    doc = next((d for d in app.documents if d.id == finding.document_id), None)
    version_no = item.document.version
    latest_version = None
    if doc is not None:
        latest_version = next((v for v in doc.versions if v.version == (version_no or doc.current_version)), None)
    page = None
    if item.page_reference:
        m = _PAGE.search(item.page_reference)
        page = int(m.group(1)) if m else None

    fields: list[ApplicantEvidenceFieldOut] = []
    has_region = False
    if latest_version is not None and page is not None:
        q = db.query(ExtractedField).filter(
            ExtractedField.document_version_id == latest_version.id,
            ExtractedField.page_number == page,
        )
        for f in q.order_by(ExtractedField.created_at).limit(12):
            bbox = None
            if None not in (f.bbox_x0, f.bbox_y0, f.bbox_x1, f.bbox_y1):
                bbox = {"x0": f.bbox_x0, "y0": f.bbox_y0, "x1": f.bbox_x1, "y1": f.bbox_y1}
                has_region = True
            value = applicant_findings_service.safe_text(f.corrected_value or f.value, 200)
            if value:
                fields.append(
                    ApplicantEvidenceFieldOut(
                        name=f.field_name.replace("_", " "),
                        value=value,
                        page_number=f.page_number,
                        bbox=bbox,
                    )
                )

    if has_region:
        note = "Highlighted regions are shown only where the reader recorded exact coordinates."
    elif page is not None:
        note = f"The finding cites page {page}. The exact position on the page was not recorded."
    elif item.snippet:
        note = "No page was recorded for this finding; the text below is what the check referred to."
    else:
        note = "No page or text location was recorded for this finding."
    return ApplicantEvidenceOut(
        finding_id=finding.id,
        reference=item.reference,
        title=item.title,
        explanation=item.explanation,
        requested_correction=item.requested_correction,
        document_id=item.document.document_id,
        document_name=item.document.name,
        version=version_no,
        current_version=item.document.current_version,
        mime_type=latest_version.mime_type if latest_version else "",
        page_count=latest_version.page_count if latest_version else None,
        page=page,
        page_reference=item.page_reference,
        snippet=item.snippet,
        fields=fields,
        clarification_id=item.clarification_id,
        location_note=note,
    )
