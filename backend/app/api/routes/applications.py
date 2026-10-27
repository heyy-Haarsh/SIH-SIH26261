from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core import runtime_config
from app.core.database import get_db
from app.core.security import ensure_application_access, get_current_user, require_roles
from app.models.application import Application
from app.models.enums import UserRole
from app.models.user import User
from app.models.validation import Finding
from app.schemas.common import (
    ApplicationCreateIn,
    ApplicantApplicationOut,
    ApplicationDetailOut,
    ApplicationSummaryOut,
    UploadPolicyOut,
    UploadResultOut,
    ValidationRunOut,
)
from app.services import (
    applicant_view_service,
    application_metrics_service,
    application_service,
    document_service,
)
from app.services.serializers import finding_to_out
from app.services.validation_service import run_validation

router = APIRouter(prefix="/applications", tags=["applications"])

def _applicant_safe_upload(result: UploadResultOut) -> UploadResultOut:
    """Applicants only learn what they can act on: whether the file was accepted, and the plain
    document check. Rule findings, hashes and run identifiers stay with scrutiny staff."""
    checks = result.file_checks or {}
    safe_checks = {
        "ok": bool(checks.get("ok", True)),
        "errors": list(checks.get("errors") or []),
        "warnings": list(checks.get("warnings") or []),
        "extension": checks.get("extension"),
        "size_bytes": checks.get("size_bytes"),
    }
    return result.model_copy(
        update={
            "findings": [],
            "file_checks": safe_checks,
        }
    )


@router.get("/upload-policy", response_model=UploadPolicyOut)
def get_upload_policy(_: User = Depends(get_current_user)):
    """Limits the browser validates against before upload (server enforces them again)."""
    from app.document_processing.ocr_processor import tesseract_status

    ocr = tesseract_status()
    return UploadPolicyOut(
        max_upload_mb=runtime_config.max_upload_mb(),
        max_upload_bytes=runtime_config.max_upload_bytes(),
        allowed_extensions=sorted(runtime_config.allowed_extensions()),
        ocr_available=bool(ocr.get("available")),
        ocr_languages=list(ocr.get("languages_usable") or []),
        marathi_supported=bool(ocr.get("marathi_supported")),
        ocr_message=str(ocr.get("message") or ""),
    )


@router.get("/metrics")
def application_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    """Counts for the officer/admin dashboards, from the same stage model as every list."""
    return application_metrics_service.application_metrics(db)


@router.get("", response_model=list[ApplicationSummaryOut])
def list_applications(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    return application_service.list_applications(db, user)


@router.post("", response_model=ApplicantApplicationOut)
def create_application(
    body: ApplicationCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    created = application_service.create_application(
        db,
        user,
        category_code=body.category_code,
        institution_name=body.institution_name,
        program_name=body.program_name,
        academic_year=body.academic_year,
    )
    # The applicant gets the narrow applicant view back, never the internal scrutiny detail.
    return applicant_view_service.get_applicant_application(db, user, created.id)


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    return application_service.get_application(db, user, application_id)


@router.post("/{application_id}/documents", response_model=UploadResultOut)
async def upload_document(
    application_id: str,
    requirement_code: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    result = document_service.upload_document(
        db,
        user,
        application_id,
        file=file,
        requirement_code=requirement_code,
    )
    return _applicant_safe_upload(result)


@router.post("/{application_id}/validation-runs", response_model=ValidationRunOut)
def create_validation_run(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    run = run_validation(db, app, triggered_by=user.id, actor_name=user.name)
    findings = db.query(Finding).filter(Finding.validation_run_id == run.id).all()
    for f in findings:
        _ = f.evidence
    status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
    return ValidationRunOut(
        validation_run_id=run.id,
        status=status_val,
        findings=[finding_to_out(f) for f in findings],
    )


@router.get("/{application_id}/report.json")
def get_application_report_json(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    from app.services.report_service import generate_application_report

    report = generate_application_report(db, application_id)
    return report.model_dump(mode="json")


@router.get("/{application_id}/report.pdf")
def get_application_report_pdf(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    from app.services.report_service import generate_application_report_pdf

    data = generate_application_report_pdf(db, application_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="scrutiny-report-{app.application_number}.pdf"'
        },
    )
