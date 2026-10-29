from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.errors import UnprocessableError
from app.core.security import ensure_application_access
from app.models.application import Application
from app.models.category import ApplicationCategory
from app.models.enums import ApplicationStatus, Priority, UserRole
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.serializers import application_detail, application_summary


def _eager():
    return [
        joinedload(Application.institution),
        joinedload(Application.category),
        joinedload(Application.documents),
        joinedload(Application.assigned_officer),
    ]


def list_applications(
    db: Session,
    user: User,
    *,
    stage: str | None = None,
    status: str | None = None,
    category_code: str | None = None,
    has_clarification_response: bool | None = None,
):
    q = db.query(Application).options(*_eager())
    if user.role == UserRole.APPLICANT:
        if not user.institution_id:
            return []
        q = q.filter(Application.institution_id == user.institution_id)
    else:
        # An applicant's unsubmitted draft is private: staff never see it until it is submitted.
        q = q.filter(Application.status != ApplicationStatus.DRAFT)
        if user.role == UserRole.OFFICER:
            # Scrutiny officers only see applications delegated to them.
            q = q.filter(Application.assigned_officer_id == user.id)
        # The regional officer sees the full region queue (assigned + unassigned).

    # Optional server-side filters — avoids loading all rows into Python for queue pages.
    if status:
        try:
            q = q.filter(Application.status == ApplicationStatus(status))
        except ValueError:
            pass  # unknown status — return all
    if category_code:
        from app.models.category import ApplicationCategory as Cat
        q = q.join(Cat, Application.category_id == Cat.id, isouter=True)
        q = q.filter(Cat.code == category_code)
    if has_clarification_response is True:
        q = q.filter(Application.status == ApplicationStatus.RESUBMITTED)

    apps = q.order_by(Application.created_at.desc()).all()
    return [application_summary(db, a) for a in apps]


def get_application(db: Session, user: User, application_id: str):
    app = (
        db.query(Application)
        .options(*_eager())
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    if user.role != UserRole.APPLICANT and app.status == ApplicationStatus.DRAFT:
        raise HTTPException(status_code=404, detail="Application not found")
    for d in app.documents:
        _ = d.versions
        for v in d.versions:
            _ = v.extracted_fields
    return application_detail(db, app)


def create_application(
    db: Session,
    user: User,
    *,
    category_code: str,
    institution_name: str,
    program_name: str,
    academic_year: str,
    save_as_draft: bool = False,
    info_values: dict | None = None,
):
    """Create an application.

    ``save_as_draft=True`` (what the applicant UI sends) creates a private draft that is not
    delegated and not visible to staff until the applicant explicitly submits it. The default
    (``False``) keeps the legacy behaviour of submitting immediately for scripted clients.
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=403, detail="Only applicants can create applications")
    if not user.institution_id:
        raise HTTPException(status_code=400, detail="Applicant has no institution")

    category = (
        db.query(ApplicationCategory).filter(ApplicationCategory.code == category_code).first()
    )
    if not category:
        raise HTTPException(status_code=400, detail=f"Unknown category_code: {category_code}")
    from app.services import category_config_service as ccs

    pub = ccs.latest_published(db, category.id) if category.is_active else None
    if pub is None:
        raise UnprocessableError(
            "This application purpose is not available right now.", code="category_unavailable"
        )

    count = db.query(Application).count() + 1
    number = f"PRM-2025-{1000 + count}"
    now = datetime.now(timezone.utc)
    app = Application(
        application_number=number,
        institution_id=user.institution_id,
        category_id=category.id,
        created_by_id=user.id,
        institution_name=institution_name,
        program_name=program_name,
        academic_year=academic_year,
        contact_email=user.email,
        config_version_id=pub.id,
        info_values=dict(info_values or {}),
        status=ApplicationStatus.DRAFT if save_as_draft else ApplicationStatus.SUBMITTED,
        priority=Priority.MEDIUM,
        submitted_at=None if save_as_draft else now,
    )
    db.add(app)
    db.flush()
    record_audit(
        db,
        action="application.created",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Created {number} for {institution_name}" + (" (draft)" if save_as_draft else ""),
        application_id=app.id,
    )
    db.commit()
    if not save_as_draft:
        # Regional Officer policy: auto-assign to the least-burdened scrutiny officer.
        from app.services import delegation_service

        delegation_service.try_auto_delegate(db, app.id)
    return get_application(db, user, app.id)


def update_draft(
    db: Session,
    user: User,
    application_id: str,
    *,
    category_code: str | None = None,
    institution_name: str | None = None,
    program_name: str | None = None,
    academic_year: str | None = None,
    info_values: dict | None = None,
):
    """Autosave target for the wizard. Only the owner's DRAFT can change; nothing else is touched.

    Changing the category recalculates the checklist. Documents already uploaded for a requirement
    the new category does not list are kept (shown as "other documents"), never deleted.
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=403, detail="Only applicants can edit a draft")
    app = db.query(Application).filter(Application.id == application_id).first()
    if app is None or app.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail={"code": "not_a_draft", "message": "Only a draft can be edited. This application was already submitted."},
        )
    changed: list[str] = []
    if category_code is not None and (app.category is None or app.category.code != category_code):
        category = db.query(ApplicationCategory).filter(ApplicationCategory.code == category_code).first()
        if not category:
            raise HTTPException(status_code=400, detail=f"Unknown category_code: {category_code}")
        from app.services import category_config_service as ccs

        app.category_id = category.id
        app.category = category
        ccs.pin_application(db, app)  # the draft follows the new purpose's published configuration
        changed.append("category")
    for name, value in (
        ("institution_name", institution_name),
        ("program_name", program_name),
        ("academic_year", academic_year),
    ):
        if value is not None and getattr(app, name) != value:
            setattr(app, name, value)
            changed.append(name)
    if info_values is not None:
        merged = dict(app.info_values or {})
        merged.update(info_values)  # never drops stored values, even for fields the category no longer asks
        if merged != (app.info_values or {}):
            app.info_values = merged
            changed.append("information")
    if changed:
        record_audit(
            db,
            action="application.draft_updated",
            actor=user.name,
            actor_id=user.id,
            actor_role=user.role.value,
            detail="Draft details changed: " + ", ".join(changed),
            application_id=app.id,
        )
        db.commit()
    return get_application(db, user, app.id)
