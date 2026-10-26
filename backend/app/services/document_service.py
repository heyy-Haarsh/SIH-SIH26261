from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.seed import DEFAULT_DOCS
from app.core.security import ensure_application_access
from app.document_processing.intake import LocalIntakeModule
from app.document_processing.orchestrator import run_extraction_for_version
from app.models.application import Application
from app.models.document import Document, DocumentVersion
from app.models.enums import DocumentStatus, UserRole, ValidationOutcome
from app.models.user import User
from app.models.validation import Finding
from app.schemas.common import UploadResultOut
from app.services.audit_service import record_audit
from app.services.serializers import finding_to_out
from app.services.validation_service import run_validation


def upload_document(
    db: Session,
    user: User,
    application_id: str,
    *,
    file: UploadFile,
    requirement_code: str,
) -> UploadResultOut:
    if user.role not in (UserRole.APPLICANT, UserRole.ADMIN):
        raise HTTPException(
            status_code=403, detail="Only applicants can upload documents in demo flow"
        )

    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)

    known = {r["code"] for r in DEFAULT_DOCS}
    if requirement_code not in known:
        raise HTTPException(status_code=400, detail=f"Unknown requirement_code: {requirement_code}")

    content = file.file.read()
    intake = LocalIntakeModule()
    result = intake.inspect(
        file_name=file.filename,
        declared_content_type=file.content_type,
        content=content,
    )
    if not result.accepted:
        raise HTTPException(
            status_code=result.rejection_status or 400,
            detail={
                "code": result.rejection_code,
                "message": result.rejection_reason,
                "fileChecks": {
                    "ok": False,
                    "errors": [result.rejection_reason],
                    "warnings": [w.message for w in result.warnings],
                    "sha256": result.sha256,
                    "source": "local_validation",
                },
            },
        )

    checks = {
        "ok": True,
        "errors": [],
        "warnings": [w.message for w in result.warnings],
        "extension": result.extension,
        "mime_type": result.mime_type,
        "size_bytes": result.size_bytes,
        "sha256": result.sha256,
        "source": "local_validation",
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in result.checks],
    }

    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    doc = (
        db.query(Document)
        .filter(
            Document.application_id == application_id,
            Document.requirement_code == requirement_code,
        )
        .first()
    )
    req_name = next(r["name"] for r in DEFAULT_DOCS if r["code"] == requirement_code)
    if not doc:
        doc = Document(
            application_id=application_id,
            requirement_code=requirement_code,
            name=req_name,
            current_version=1,
            status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        db.flush()
        version_no = 1
    else:
        version_no = doc.current_version + 1
        doc.current_version = version_no
        doc.status = DocumentStatus.REPLACED

    safe_name = result.file_name or Path(file.filename or "upload.bin").name
    storage_name = (
        f"{application_id}_{requirement_code}_v{version_no}_{result.sha256[:12]}_{safe_name}"
    )
    storage_path = settings.upload_path / storage_name
    storage_path.write_bytes(content)

    version = DocumentVersion(
        document_id=doc.id,
        version=version_no,
        file_name=safe_name,
        extension=result.extension,
        mime_type=result.mime_type,
        declared_content_type=file.content_type,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
        storage_path=str(storage_path),
        page_count=result.page_count,
        file_checks=checks,
        validation_outcome=(
            ValidationOutcome.WARNING if result.warnings else ValidationOutcome.PASS
        ),
        uploaded_by_id=user.id,
    )
    db.add(version)
    db.flush()

    record_audit(
        db,
        action="document.uploaded",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Uploaded {safe_name} as {requirement_code} v{version_no}",
        application_id=application_id,
    )
    db.commit()

    extraction_run_id = None
    extraction_status = None
    validation_run_id = None
    findings_out = []

    # Reload version after commit
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version.id).one()
    doc = db.query(Document).filter(Document.id == doc.id).one()

    if settings.auto_extract_on_upload:
        ext_run = run_extraction_for_version(
            db,
            version,
            application_id=application_id,
            selected_requirement_code=requirement_code,
            triggered_by_id=user.id,
            force=False,
        )
        db.commit()
        extraction_run_id = ext_run.id
        extraction_status = (
            ext_run.status.value if hasattr(ext_run.status, "value") else str(ext_run.status)
        )

    app = db.query(Application).filter(Application.id == application_id).first()
    val_run = run_validation(db, app, triggered_by=user.id, actor_name=user.name)
    validation_run_id = val_run.id

    if extraction_run_id:
        from app.models.extraction import ExtractionRun

        ext = db.query(ExtractionRun).filter(ExtractionRun.id == extraction_run_id).first()
        if ext:
            ext.validation_run_id = validation_run_id
            db.add(ext)
            db.commit()

    findings_db = db.query(Finding).filter(Finding.validation_run_id == val_run.id).all()
    for f in findings_db:
        _ = f.evidence
    findings_out = [finding_to_out(f) for f in findings_db]

    return UploadResultOut(
        document_id=doc.id,
        validation_run_id=validation_run_id,
        extraction_run_id=extraction_run_id,
        extraction_status=extraction_status,
        findings=findings_out,
        file_checks=checks,
    )
