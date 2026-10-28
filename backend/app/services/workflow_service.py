"""Application scrutiny workflow transitions with RBAC and audit.

Statuses (Phase 5): submitted → processing → under_scrutiny →
clarification_required ↔ resubmitted → recommended | rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.application import Application
from app.models.base import utcnow
from app.models.enums import (
    ApplicationStatus,
    DeficiencyStatus,
    FindingStatus,
    ReviewDecisionType,
    UserRole,
)
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.user import User
from app.models.validation import Finding
from app.services.audit_service import record_audit
from app.services import scoring as scoring_service
from app.services.serializers import application_detail

# Role → allowed actions are enforced per method; transitions encode valid edges.
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: {ApplicationStatus.SUBMITTED},
    ApplicationStatus.SUBMITTED: {
        ApplicationStatus.PROCESSING,
        ApplicationStatus.UNDER_SCRUTINY,
    },
    ApplicationStatus.PROCESSING: {
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.CLARIFICATION_REQUIRED,
    },
    ApplicationStatus.UNDER_SCRUTINY: {
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.PROCESSING,  # re-run processing
    },
    ApplicationStatus.CLARIFICATION_REQUIRED: {
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.UNDER_SCRUTINY,  # officer may cancel clarification
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.RESUBMITTED: {
        ApplicationStatus.PROCESSING,
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.RECOMMENDED: set(),  # terminal unless admin reopen (not implemented)
    ApplicationStatus.REJECTED: set(),
    # Legacy → Phase 5
    ApplicationStatus.AWAITING_REVIEW: {
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.PROCESSING,
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.UNDER_REVIEW: {
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.DEFICIENCY: {
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.MANUAL_REVIEW: {
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.APPROVED: set(),
}


def _get_app(db: Session, application_id: str) -> Application:
    app = (
        db.query(Application)
        .options(
            joinedload(Application.category),
            joinedload(Application.documents),
            joinedload(Application.institution),
            joinedload(Application.assigned_officer),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise NotFoundError("Application not found")
    return app


def _ensure_officer_may_act(app: Application, user: User, *, action: str) -> None:
    """Prevent concurrent officer actions once an application is claimed."""
    if user.role == UserRole.REGIONAL_OFFICER:
        return
    if app.assigned_officer_id and app.assigned_officer_id != user.id:
        raise ConflictError(
            f"Another officer is assigned; cannot {action} concurrently. "
            "Admin override required, or claim a different application."
        )


def _transition(
    db: Session,
    app: Application,
    new_status: ApplicationStatus,
    *,
    actor: User,
    note: str = "",
    action: str = "workflow.transition",
) -> None:
    current = app.status
    allowed = VALID_TRANSITIONS.get(current, set())
    if new_status not in allowed and new_status != current:
        raise UnprocessableError(
            f"Invalid transition: {current.value} → {new_status.value}. "
            f"Allowed: {sorted(s.value for s in allowed) or 'none (terminal)'}"
        )
    previous = current.value if hasattr(current, "value") else str(current)
    app.status = new_status
    app.last_transition_at = utcnow()
    app.last_transition_note = note or None
    record_audit(
        db,
        action=action,
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"{previous} → {new_status.value}" + (f"; {note}" if note else ""),
        application_id=app.id,
    )


def mark_processing(db: Session, app: Application, actor: User | None = None) -> None:
    """Called when validation/forensics pipeline starts — best-effort status update."""
    if app.status in (
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.AWAITING_REVIEW,
        ApplicationStatus.UNDER_SCRUTINY,
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.MANUAL_REVIEW,
    ):
        prev = app.status
        if ApplicationStatus.PROCESSING in VALID_TRANSITIONS.get(prev, set()) or prev in (
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.RESUBMITTED,
            ApplicationStatus.AWAITING_REVIEW,
            ApplicationStatus.UNDER_SCRUTINY,
            ApplicationStatus.UNDER_REVIEW,
            ApplicationStatus.MANUAL_REVIEW,
        ):
            app.status = ApplicationStatus.PROCESSING
            app.last_transition_at = utcnow()
            app.last_transition_note = "Automatic: processing started"
            if actor:
                record_audit(
                    db,
                    action="workflow.processing_started",
                    actor=actor.name,
                    actor_id=actor.id,
                    actor_role=actor.role.value,
                    detail=f"{prev.value} → processing",
                    application_id=app.id,
                )


def mark_under_scrutiny(db: Session, app: Application, actor: User | None = None) -> None:
    if app.status in (
        ApplicationStatus.PROCESSING,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.AWAITING_REVIEW,
    ):
        prev = app.status
        app.status = ApplicationStatus.UNDER_SCRUTINY
        app.last_transition_at = utcnow()
        app.last_transition_note = "Automatic: processing completed — under scrutiny"
        if actor:
            record_audit(
                db,
                action="workflow.under_scrutiny",
                actor=actor.name,
                actor_id=actor.id,
                actor_role=actor.role.value,
                detail=f"{prev.value} → under_scrutiny",
                application_id=app.id,
            )


def start_scrutiny(db: Session, user: User, application_id: str) -> dict:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers may start scrutiny.")
    app = _get_app(db, application_id)
    if app.assigned_officer_id and app.assigned_officer_id != user.id and user.role != UserRole.REGIONAL_OFFICER:
        raise ConflictError(
            "Another officer is assigned to this application. Concurrent review requires admin override."
        )
    app.assigned_officer_id = user.id
    if app.status in (
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.AWAITING_REVIEW,
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.PROCESSING,
    ):
        _transition(
            db,
            app,
            ApplicationStatus.UNDER_SCRUTINY,
            actor=user,
            note="Officer claimed application for scrutiny",
            action="workflow.start_scrutiny",
        )
    elif app.status == ApplicationStatus.UNDER_SCRUTINY:
        record_audit(
            db,
            action="workflow.claim",
            actor=user.name,
            actor_id=user.id,
            actor_role=user.role.value,
            detail="Officer claimed already under-scrutiny application",
            application_id=app.id,
        )
    else:
        raise UnprocessableError(f"Cannot start scrutiny from status {app.status.value}")

    scoring_service.apply_score_to_application(db, app)
    db.commit()
    return application_detail(db, _get_app(db, application_id))


def request_clarification(
    db: Session,
    user: User,
    application_id: str,
    *,
    title: str,
    description: str,
    finding_ids: list[str] | None = None,
) -> dict:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers may request clarification.")
    title = (title or "").strip()
    description = (description or "").strip()
    if len(title) < 3 or len(description) < 5:
        raise UnprocessableError("title (≥3) and description (≥5) are required.")

    app = _get_app(db, application_id)
    _ensure_officer_may_act(app, user, action="request clarification")
    _transition(
        db,
        app,
        ApplicationStatus.CLARIFICATION_REQUIRED,
        actor=user,
        note=title,
        action="workflow.clarification_requested",
    )

    notice = DeficiencyNotice(
        application_id=app.id,
        issued_by_id=user.id,
        finding_id=(finding_ids[0] if finding_ids else None),
        title=title,
        description=description,
        status=DeficiencyStatus.OPEN,
    )
    db.add(notice)
    db.flush()

    db.add(
        ReviewDecision(
            application_id=app.id,
            author_id=user.id,
            author_role=user.role,
            decision_type=ReviewDecisionType.CLARIFICATION,
            content=f"{title}\n\n{description}",
        )
    )
    scoring_service.apply_score_to_application(db, app)
    db.commit()
    return application_detail(db, _get_app(db, application_id))


def respond_deficiency(
    db: Session,
    user: User,
    deficiency_id: str,
    *,
    response: str,
) -> DeficiencyNotice:
    if user.role != UserRole.APPLICANT:
        raise ForbiddenError("Only applicants may respond to deficiencies.")
    response = (response or "").strip()
    if len(response) < 5:
        raise UnprocessableError("Response must be at least 5 characters.")

    notice = db.query(DeficiencyNotice).filter(DeficiencyNotice.id == deficiency_id).first()
    if not notice:
        raise NotFoundError("Deficiency notice not found")
    app = _get_app(db, notice.application_id)
    if user.institution_id != app.institution_id:
        raise NotFoundError("Deficiency notice not found")
    if notice.status != DeficiencyStatus.OPEN:
        raise UnprocessableError("Deficiency is not open.")

    notice.status = DeficiencyStatus.RESPONDED
    notice.applicant_response = response
    notice.responded_at = utcnow()
    record_audit(
        db,
        action="workflow.deficiency_responded",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"deficiency={notice.id}; {response[:200]}",
        application_id=app.id,
    )
    scoring_service.apply_score_to_application(db, app)
    db.commit()
    db.refresh(notice)
    return notice


MAX_RESUBMIT_NOTE = 2000


def resubmit_blockers(db: Session, app: Application) -> list[str]:
    """Plain-language reasons an applicant cannot resubmit yet (empty list = ready)."""
    open_notices = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == app.id,
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
        )
        .order_by(DeficiencyNotice.created_at)
        .all()
    )
    return [f"Respond to the clarification request: “{n.title}”" for n in open_notices]


def resubmit(db: Session, user: User, application_id: str, *, note: str = "") -> dict:
    if user.role != UserRole.APPLICANT:
        raise ForbiddenError("Only applicants may resubmit.")
    app = _get_app(db, application_id)
    if user.institution_id != app.institution_id:
        raise NotFoundError("Application not found")
    if app.status not in (
        ApplicationStatus.CLARIFICATION_REQUIRED,
        ApplicationStatus.DEFICIENCY,
    ):
        raise UnprocessableError(
            "Resubmit is only allowed while the officer's clarification request is open.",
            code="resubmit_not_allowed",
        )
    note = (note or "").strip()
    if len(note) > MAX_RESUBMIT_NOTE:
        raise UnprocessableError(
            f"The resubmission note is too long (max {MAX_RESUBMIT_NOTE} characters).",
            code="note_too_long",
        )
    blockers = resubmit_blockers(db, app)
    if blockers:
        # Every open clarification must be answered before the officer sees the application again.
        raise UnprocessableError(
            "Resubmission is blocked: " + "; ".join(blockers),
            code="open_clarifications",
            extra={"blockers": blockers},
        )

    # Close responded deficiencies (the applicant's response stays on the record)
    responded = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == app.id,
            DeficiencyNotice.status == DeficiencyStatus.RESPONDED,
        )
        .all()
    )
    for n in responded:
        n.status = DeficiencyStatus.CLOSED
        n.resolved_at = utcnow()

    _transition(
        db,
        app,
        ApplicationStatus.RESUBMITTED,
        actor=user,
        note=note or "Applicant resubmitted after clarification",
        action="workflow.resubmitted",
    )
    db.add(
        ReviewDecision(
            application_id=app.id,
            author_id=user.id,
            author_role=user.role,
            decision_type=ReviewDecisionType.RESUBMIT,
            content=note or "Resubmitted with corrected documents / responses.",
        )
    )

    # Persist the resubmission itself first: if reprocessing fails the applicant's response,
    # the closed notices and the RESUBMITTED status must not be lost (officer can re-run).
    db.commit()

    # Re-run full processing; preserves prior findings in DB (new validation run adds new ones)
    from app.services.validation_service import run_validation

    try:
        mark_processing(db, _get_app(db, application_id), actor=user)
        db.flush()
        run_validation(db, _get_app(db, application_id), triggered_by=user.id, actor_name=user.name)
    except Exception as exc:  # noqa: BLE001 — never lose the resubmission
        db.rollback()
        app = _get_app(db, application_id)
        app.status = ApplicationStatus.RESUBMITTED
        app.last_transition_at = utcnow()
        app.last_transition_note = "Reprocessing failed after resubmission; officer re-run needed."
        record_audit(
            db,
            action="workflow.resubmit_reprocess_failed",
            actor="system",
            actor_role="system",
            detail=f"{exc.__class__.__name__} during automatic re-validation",
            application_id=app.id,
        )
        db.commit()
        return application_detail(db, _get_app(db, application_id))

    # run_validation commits; reload and ensure we never leave the application in PROCESSING
    app = _get_app(db, application_id)
    if app.status == ApplicationStatus.PROCESSING:
        mark_under_scrutiny(db, app, actor=user)
        scoring_service.apply_score_to_application(db, app)
        db.commit()
    return application_detail(db, _get_app(db, application_id))


def resolve_finding(
    db: Session,
    user: User,
    finding_id: str,
    *,
    status: FindingStatus,
    reason: str,
) -> Finding:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers may resolve findings.")
    if status not in (FindingStatus.RESOLVED, FindingStatus.WAIVED, FindingStatus.ACCEPTED):
        raise UnprocessableError("status must be resolved, waived, or accepted")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise UnprocessableError("A reason of at least 5 characters is required.")

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise NotFoundError("Finding not found")
    app = _get_app(db, finding.application_id)
    _ensure_officer_may_act(app, user, action="resolve findings")
    # Preserve original severity/outcome; only status + officer note change.
    # waived = still on record, not blocking this stage; resolved = fixed after check;
    # accepted = officer accepts the finding as recorded without requiring a re-upload.
    finding.status = status
    finding.resolution_reason = reason
    finding.resolved_at = utcnow()
    record_audit(
        db,
        action="workflow.finding_resolved",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"finding={finding.id}; status={status.value}; reason={reason[:200]}",
        application_id=finding.application_id,
    )
    scoring_service.apply_score_to_application(db, app)
    db.commit()
    db.refresh(finding)
    return finding


def record_recommendation(
    db: Session,
    user: User,
    application_id: str,
    *,
    recommend: bool,
    reason: str,
) -> dict:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers may record recommendations.")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise UnprocessableError("A reason of at least 5 characters is required.")

    app = _get_app(db, application_id)
    if app.assigned_officer_id and app.assigned_officer_id != user.id and user.role != UserRole.REGIONAL_OFFICER:
        raise ConflictError("Another officer is assigned; cannot finalize concurrent review.")

    target = ApplicationStatus.RECOMMENDED if recommend else ApplicationStatus.REJECTED
    _transition(
        db,
        app,
        target,
        actor=user,
        note=reason,
        action="workflow.recommended" if recommend else "workflow.rejected",
    )
    db.add(
        ReviewDecision(
            application_id=app.id,
            author_id=user.id,
            author_role=user.role,
            decision_type=ReviewDecisionType.RECOMMEND if recommend else ReviewDecisionType.REJECT,
            content=reason,
        )
    )
    # Refresh final summary snapshot
    scoring_service.apply_score_to_application(db, app)
    summary = dict(app.scrutiny_summary or {})
    summary["finalDecision"] = target.value
    summary["finalDecisionReason"] = reason
    summary["finalDecisionAt"] = datetime.now(timezone.utc).isoformat()
    summary["finalDecisionBy"] = user.name
    app.scrutiny_summary = summary
    db.commit()
    return application_detail(db, _get_app(db, application_id))


def add_note(db: Session, user: User, application_id: str, *, content: str) -> dict:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers may add review notes.")
    content = (content or "").strip()
    if len(content) < 3:
        raise UnprocessableError("Note content is required.")
    app = _get_app(db, application_id)
    _ensure_officer_may_act(app, user, action="add notes")
    db.add(
        ReviewDecision(
            application_id=app.id,
            author_id=user.id,
            author_role=user.role,
            decision_type=ReviewDecisionType.NOTE,
            content=content,
        )
    )
    record_audit(
        db,
        action="workflow.note_added",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=content[:300],
        application_id=app.id,
    )
    db.commit()
    return application_detail(db, _get_app(db, application_id))


def list_deficiencies(db: Session, user: User, application_id: str | None = None) -> list[DeficiencyNotice]:
    q = db.query(DeficiencyNotice).order_by(DeficiencyNotice.created_at.desc())
    if application_id:
        app = _get_app(db, application_id)
        if user.role == UserRole.APPLICANT and user.institution_id != app.institution_id:
            raise NotFoundError("Application not found")
        q = q.filter(DeficiencyNotice.application_id == application_id)
    elif user.role == UserRole.APPLICANT:
        if not user.institution_id:
            return []
        q = q.join(Application).filter(Application.institution_id == user.institution_id)
    return q.all()


def refresh_summary(db: Session, user: User, application_id: str) -> dict:
    app = _get_app(db, application_id)
    from app.core.security import ensure_application_access

    ensure_application_access(user, app)
    scoring_service.apply_score_to_application(db, app)
    db.commit()
    return application_detail(db, _get_app(db, application_id))
