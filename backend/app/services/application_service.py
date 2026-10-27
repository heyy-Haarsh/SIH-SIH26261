from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

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


def list_applications(db: Session, user: User):
    q = db.query(Application).options(*_eager())
    if user.role == UserRole.APPLICANT:
        if not user.institution_id:
            return []
        q = q.filter(Application.institution_id == user.institution_id)
    elif user.role == UserRole.ADMIN:
        # Admins manage config; application list is officer-oriented. Still allow read for demo.
        pass
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
):
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=403, detail="Only applicants can create applications")
    if not user.institution_id:
        raise HTTPException(status_code=400, detail="Applicant has no institution")

    category = (
        db.query(ApplicationCategory).filter(ApplicationCategory.code == category_code).first()
    )
    if not category:
        raise HTTPException(status_code=400, detail=f"Unknown category_code: {category_code}")

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
        status=ApplicationStatus.SUBMITTED,
        priority=Priority.MEDIUM,
        submitted_at=now,
    )
    db.add(app)
    db.flush()
    record_audit(
        db,
        action="application.created",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Created {number} for {institution_name}",
        application_id=app.id,
    )
    db.commit()
    return get_application(db, user, app.id)
