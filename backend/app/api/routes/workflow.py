"""Scrutiny workflow APIs: claim, clarify, resubmit, recommend, deficiencies."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ensure_application_access, get_current_user, require_roles
from app.models.application import Application
from app.models.enums import FindingStatus, UserRole
from app.models.user import User
from app.schemas.common import (
    ApplicantApplicationOut,
    ApplicationDetailOut,
    DeficiencyOut,
    DeficiencyRespondIn,
    FindingOut,
    FindingResolveIn,
    FindingTransitionIn,
    FindingTransitionOut,
    WorkflowClarificationIn,
    WorkflowDecisionIn,
    WorkflowNoteIn,
    WorkflowResubmitIn,
)
from app.services import applicant_view_service, finding_lifecycle, workflow_service
from app.services.serializers import deficiency_to_out, finding_to_out

router = APIRouter(tags=["workflow"])


@router.post("/applications/{application_id}/scrutiny/start", response_model=ApplicationDetailOut)
def start_scrutiny(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if app:
        ensure_application_access(user, app)
    return workflow_service.start_scrutiny(db, user, application_id)


@router.post(
    "/applications/{application_id}/scrutiny/clarification",
    response_model=ApplicationDetailOut,
)
def request_clarification(
    application_id: str,
    body: WorkflowClarificationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    return workflow_service.request_clarification(
        db,
        user,
        application_id,
        title=body.title,
        description=body.description,
        finding_ids=body.finding_ids,
        requires_replacement=body.requires_replacement,
        due_date=body.due_date,
    )


@router.post(
    "/applications/{application_id}/scrutiny/decision",
    response_model=ApplicationDetailOut,
)
def record_decision(
    application_id: str,
    body: WorkflowDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    return workflow_service.record_recommendation(
        db, user, application_id, recommend=body.recommend, reason=body.reason
    )


@router.post("/applications/{application_id}/scrutiny/notes", response_model=ApplicationDetailOut)
def add_note(
    application_id: str,
    body: WorkflowNoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    return workflow_service.add_note(db, user, application_id, content=body.content)


@router.post("/applications/{application_id}/resubmit", response_model=ApplicantApplicationOut)
def resubmit(
    application_id: str,
    body: WorkflowResubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    # Applicants get the narrow applicant view back — never the internal scrutiny detail.
    workflow_service.resubmit(db, user, application_id, note=body.note)
    return applicant_view_service.get_applicant_application(db, user, application_id)


@router.post(
    "/applications/{application_id}/scrutiny/refresh-summary",
    response_model=ApplicationDetailOut,
)
def refresh_summary(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    return workflow_service.refresh_summary(db, user, application_id)


@router.get("/deficiencies", response_model=list[DeficiencyOut])
def list_all_deficiencies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notices = workflow_service.list_deficiencies(db, user)
    # Attach application numbers when possible
    out = []
    for n in notices:
        app = db.query(Application).filter(Application.id == n.application_id).first()
        out.append(deficiency_to_out(n, app.application_number if app else None))
    return out


@router.get("/applications/{application_id}/deficiencies", response_model=list[DeficiencyOut])
def list_app_deficiencies(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notices = workflow_service.list_deficiencies(db, user, application_id=application_id)
    app = db.query(Application).filter(Application.id == application_id).first()
    num = app.application_number if app else None
    return [deficiency_to_out(n, num) for n in notices]


@router.post("/deficiencies/{deficiency_id}/respond", response_model=DeficiencyOut)
def respond_deficiency(
    deficiency_id: str,
    body: DeficiencyRespondIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    notice = workflow_service.respond_deficiency(
        db, user, deficiency_id, response=body.response
    )
    app = db.query(Application).filter(Application.id == notice.application_id).first()
    return deficiency_to_out(notice, app.application_number if app else None)


@router.post("/findings/{finding_id}/resolve", response_model=FindingOut)
def resolve_finding(
    finding_id: str,
    body: FindingResolveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    try:
        status = FindingStatus(body.status.strip().lower())
    except ValueError as exc:
        from app.core.errors import UnprocessableError

        raise UnprocessableError("status must be resolved, waived, or accepted") from exc
    finding = workflow_service.resolve_finding(
        db, user, finding_id, status=status, reason=body.reason
    )
    return finding_to_out(finding)

@router.post("/findings/{finding_id}/transition", response_model=FindingOut)
def transition_finding(
    finding_id: str,
    body: FindingTransitionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    """Officer lifecycle move (under review, request clarification, reopen, close) with history."""
    try:
        status = FindingStatus(body.status.strip().lower())
    except ValueError as exc:
        from app.core.errors import UnprocessableError

        raise UnprocessableError(
            "status must be one of: " + ", ".join(s.value for s in FindingStatus)
        ) from exc
    finding = workflow_service.transition_finding(
        db, user, finding_id, status=status, reason=body.reason
    )
    return finding_to_out(finding)


@router.get("/findings/{finding_id}/history", response_model=list[FindingTransitionOut])
def finding_history(
    finding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    from app.core.errors import NotFoundError
    from app.models.validation import Finding

    if db.query(Finding.id).filter(Finding.id == finding_id).first() is None:
        raise NotFoundError("Finding not found")
    return finding_lifecycle.history(db, finding_id)