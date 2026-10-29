"""Applicant pre-submission readiness and the explicit, idempotent submit action.

Readiness is computed on the server from the requirement catalogue and the applicant-safe
document check (type match / clarity). It deliberately exposes no scores, rule codes or forensic
detail. It is a pre-check to help the applicant fix obvious problems — it is NOT a statement that
the application is compliant or that any document is authentic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.core.security import ensure_application_access
from app.models.application import Application
from app.models.enums import ApplicationStatus, UserRole
from app.models.user import User
from app.schemas.submission import ReadinessItemOut, ReadinessOut, SubmitResultOut
from app.services import applicant_view_service as view
from app.services.audit_service import record_audit

# The institution's own attestations. They are not regulatory declarations and are not invented
# by the interface: the server lists them, and the audit trail records that they were confirmed.
DECLARATIONS = [
    "I confirm that the details and documents in this application are accurate and complete to the best of my knowledge.",
    "I am authorised to submit this application on behalf of the institution.",
]

LIMITATIONS = [
    "These checks are an automatic pre-check on file type and legibility only. They do not "
    "confirm that a document is genuine or that the application meets AICTE requirements.",
    "Authenticity and compliance are assessed by the scrutiny officer after submission; "
    "verification against issuing authorities may be unavailable or simulated in this environment.",
]


def _load(db: Session, user: User, application_id: str) -> Application:
    if user.role != UserRole.APPLICANT:
        raise ForbiddenError("Only applicants can submit applications.")
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
    if app is None:
        raise NotFoundError("Application not found.")
    ensure_application_access(user, app)
    return app


def _status(app: Application) -> str:
    return app.status.value if hasattr(app.status, "value") else str(app.status)


def compute_readiness(db: Session, app: Application) -> ReadinessOut:
    must_fix: list[ReadinessItemOut] = []
    review: list[ReadinessItemOut] = []

    for label, value in (
        ("Institution name", app.institution_name),
        ("Program name", app.program_name),
        ("Academic year", app.academic_year),
    ):
        if not (value or "").strip():
            must_fix.append(
                ReadinessItemOut(
                    code="missing_details",
                    title=f"{label} is missing",
                    detail="Enter it in the Details step.",
                )
            )

    from app.services import category_config_service as ccs

    snap = ccs.pinned_snapshot(app)
    if snap is None:
        must_fix.append(
            ReadinessItemOut(
                code="category_config_unavailable",
                title="This application purpose has no usable configuration",
                detail="The configuration for the selected purpose is unavailable. Choose another purpose or try again later; you cannot submit against an incomplete configuration.",
            )
        )
    else:
        for key, message in ccs.validate_info_values(ccs.effective_info_fields(app), app.info_values or {}).items():
            must_fix.append(
                ReadinessItemOut(code="missing_information", title=message, detail="Update it in the Details step.")
            )

    for row in view._requirement_rows(db, app):
        if row.document is None:
            if row.mandatory:
                must_fix.append(
                    ReadinessItemOut(
                        code="missing_document",
                        title=f"{row.name} has not been uploaded",
                        detail="This document is mandatory for your application category.",
                        requirement_code=row.code,
                    )
                )
            else:
                review.append(
                    ReadinessItemOut(
                        code="optional_missing",
                        title=f"{row.name} (optional) has not been uploaded",
                        detail="Optional, but providing it can avoid a clarification request.",
                        requirement_code=row.code,
                    )
                )
            continue

        check = row.document.document_check
        if check is None:
            continue
        if check.clarity == "unreadable":
            must_fix.append(
                ReadinessItemOut(
                    code="unreadable_document",
                    title=f"{row.name} could not be read",
                    detail=check.clarity_message
                    or "Upload a clearer or higher-resolution copy of this document.",
                    requirement_code=row.code,
                )
            )
        elif check.clarity == "unclear":
            review.append(
                ReadinessItemOut(
                    code="unclear_document",
                    title=f"{row.name} may be hard to read",
                    detail=check.clarity_message
                    or "A clearer copy reduces the chance of a clarification request.",
                    requirement_code=row.code,
                )
            )
        if check.type_match == "mismatch":
            review.append(
                ReadinessItemOut(
                    code="document_type_mismatch",
                    title=f"{row.name} may be the wrong document",
                    detail=check.type_match_message
                    or "The file does not look like the requested document type.",
                    requirement_code=row.code,
                )
            )
        elif check.type_match == "unclear":
            review.append(
                ReadinessItemOut(
                    code="document_type_unclear",
                    title=f"We could not confirm the type of {row.name}",
                    detail=check.type_match_message
                    or "Please confirm this is the document requested.",
                    requirement_code=row.code,
                )
            )

    status = _status(app)
    is_draft = app.status == ApplicationStatus.DRAFT
    return ReadinessOut(
        application_id=app.id,
        status=status,
        is_draft=is_draft,
        must_fix=must_fix,
        review_recommended=review,
        limitations=list(LIMITATIONS),
        can_submit=is_draft and not must_fix,
        declarations=list(DECLARATIONS),
    )


def get_readiness(db: Session, user: User, application_id: str) -> ReadinessOut:
    return compute_readiness(db, _load(db, user, application_id))


def submit_application(
    db: Session, user: User, application_id: str, *, confirm_declarations: bool = False
) -> SubmitResultOut:
    """Move a draft to submitted exactly once.

    The draft→submitted claim is a single conditional UPDATE, so two concurrent or repeated
    requests cannot both succeed: the loser sees ``already_submitted=True`` and nothing else
    (no second audit entry, delegation, or processing run) happens.
    """
    app = _load(db, user, application_id)

    if app.status != ApplicationStatus.DRAFT:
        return SubmitResultOut(
            application_id=app.id,
            status=_status(app),
            already_submitted=True,
            submitted_at=app.submitted_at,
            message="This application has already been submitted.",
        )

    if not confirm_declarations:
        raise UnprocessableError(
            "Confirm the declarations before submitting.", code="declaration_required"
        )

    from app.services import category_config_service as ccs

    # While still a draft, the application follows the purpose's latest published configuration;
    # from submission onwards it is frozen on the configuration it was submitted under.
    if ccs.pin_application(db, app):
        record_audit(
            db,
            action="application.config_pinned",
            actor=user.name,
            actor_id=user.id,
            actor_role=user.role.value,
            detail=f"Application pinned to configuration v{app.config_version.version} at submission",
            application_id=app.id,
        )

    readiness = compute_readiness(db, app)
    if readiness.must_fix:
        raise UnprocessableError(
            "The application cannot be submitted until the required items are fixed: "
            + "; ".join(item.title for item in readiness.must_fix),
            code="not_ready",
        )

    now = datetime.now(timezone.utc)
    claimed = (
        db.query(Application)
        .filter(Application.id == app.id, Application.status == ApplicationStatus.DRAFT)
        .update(
            {
                Application.status: ApplicationStatus.SUBMITTED,
                Application.submitted_at: now,
                Application.last_transition_at: now,
                Application.last_transition_note: "Submitted by applicant",
            },
            synchronize_session=False,
        )
    )
    if not claimed:
        db.rollback()
        db.expire_all()
        fresh = _load(db, user, application_id)
        return SubmitResultOut(
            application_id=fresh.id,
            status=_status(fresh),
            already_submitted=True,
            submitted_at=fresh.submitted_at,
            message="This application has already been submitted.",
        )

    record_audit(
        db,
        action="application.submitted",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"draft → submitted ({app.application_number}); declarations confirmed",
        application_id=app.id,
    )
    from app.services import notification_service

    notification_service.notify_applicants(
        db,
        app,
        kind="application_submitted",
        title=f"{app.application_number} submitted for scrutiny",
        body="A scrutiny officer will review it. You will be notified if anything is needed.",
    )
    db.commit()

    # Hand over to scrutiny: assign an officer, then run the full pipeline once on the final
    # document set so the officer opens a complete, scored case.
    from app.services import delegation_service
    from app.services.validation_service import run_validation

    delegation_service.try_auto_delegate(db, app.id)
    fresh = db.query(Application).filter(Application.id == app.id).first()
    warnings: list[str] = []
    try:
        run_validation(db, fresh, triggered_by=user.id, actor_name=user.name)
    except Exception as exc:  # noqa: BLE001 — never lose a submission to a pipeline fault
        db.rollback()
        warnings.append(
            f"Automatic processing did not complete ({exc.__class__.__name__}); "
            "your submission is recorded and a scrutiny officer will review it."
        )
    db.expire_all()
    fresh = db.query(Application).filter(Application.id == app.id).first()
    return SubmitResultOut(
        application_id=fresh.id,
        status=_status(fresh),
        already_submitted=False,
        submitted_at=fresh.submitted_at,
        message="Application submitted for scrutiny.",
        warnings=warnings,
    )
