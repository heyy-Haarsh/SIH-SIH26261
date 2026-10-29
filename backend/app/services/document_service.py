from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core import runtime_config
from app.core.config import get_settings
from app.core.seed import DEFAULT_DOCS
from app.core.security import ensure_application_access
from app.document_processing.intake import LocalIntakeModule
from app.document_processing.orchestrator import run_extraction_for_version
from app.models.application import Application
from app.models.document import Document, DocumentVersion
from app.models.enums import ApplicationStatus, DocumentStatus, ExtractionRunStatus, UserRole, ValidationOutcome
from app.models.user import User
from app.models.validation import Finding
from app.schemas.common import UploadResultOut
from app.services.audit_service import record_audit
from app.services.serializers import finding_to_out
from app.services.validation_service import run_validation

_CHUNK = 1024 * 1024


def _requirement_catalog(app: Application) -> list[dict]:
    """The checklist the application is judged by: its pinned configuration snapshot."""
    from app.services import category_config_service

    out: list[dict] = []
    for item in category_config_service.effective_requirements(app):
        code = (item.get("code") or "").strip()
        if not code:
            continue
        out.append(
            {
                "id": item.get("id"),
                "code": code,
                "name": (item.get("name") or code).strip(),
                "mandatory": bool(item.get("mandatory", True)),
                "allowed_types": list(item.get("allowed_types") or item.get("allowedTypes") or []),
                "max_size_mb": item.get("max_size_mb"),
            }
        )
    return out or list(DEFAULT_DOCS)

def _retire_previous_results(db: Session, doc: Document, new_version: int) -> bool:
    """Mark results for earlier versions stale. Returns True when a verification had run before."""
    from app.models.doc_verification import DocumentVerificationCheck
    from app.models.enums import (
        DocumentReviewStatus,
        ExternalVerificationLayerStatus,
        RuleValidationStatus,
    )

    had_run = doc.latest_verification_run_id is not None
    doc.rule_validation_status = RuleValidationStatus.PENDING
    doc.external_verification_status = ExternalVerificationLayerStatus.PENDING
    doc.review_status = DocumentReviewStatus.PENDING
    doc.latest_verification_run_id = None
    for check in db.query(DocumentVerificationCheck).filter(
        DocumentVerificationCheck.document_id == doc.id, DocumentVerificationCheck.status == "open"
    ):
        check.status = "superseded"
        check.resolution_reason = f"Replaced by version {new_version}; re-checked on the new version."
    return had_run


def _notify_processing(db: Session, app: Application, doc_name: str, version_no: int, state: str, message: str) -> None:
    """Tell the institution what happened to a file they uploaded (in-app only)."""
    from app.services import notification_service

    is_draft = app.status == ApplicationStatus.DRAFT
    if state == "ready" and is_draft:
        return  # the wizard already shows this inline; avoid noise while drafting
    kind = "processing_failed" if state == "failed" else "processing_completed"
    title = {
        "ready": f"{doc_name} (v{version_no}) was read successfully",
        "limited": f"{doc_name} (v{version_no}) was read with limitations",
        "failed": f"{doc_name} (v{version_no}) could not be read automatically",
    }.get(state, f"{doc_name} (v{version_no}) was processed")
    notification_service.notify_applicants(db, app, kind=kind, title=title, body=message)


def _read_upload_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload in chunks; reject before buffering an oversized body fully."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "file_too_large",
                    "message": f"File exceeds the {max_bytes / (1024 * 1024):g} MB size limit.",
                },
            )
        chunks.append(chunk)
    return b"".join(chunks)


def upload_document(
    db: Session,
    user: User,
    application_id: str,
    *,
    file: UploadFile,
    requirement_code: str,
) -> UploadResultOut:
    if user.role not in (UserRole.APPLICANT, UserRole.REGIONAL_OFFICER):
        raise HTTPException(
            status_code=403, detail="Only applicants can upload documents in demo flow"
        )

    from sqlalchemy.orm import joinedload

    app = (
        db.query(Application)
        .options(joinedload(Application.category))
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    if app.status in (
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.APPROVED,
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "application_closed",
                "message": "This application has a final decision; documents can no longer be changed.",
            },
        )

    catalog = _requirement_catalog(app)
    known = {r["code"] for r in catalog}
    if requirement_code not in known:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unknown_requirement",
                "message": (
                    f"Requirement '{requirement_code}' is not on the checklist for this "
                    f"application category. Choose a document from the category requirements."
                ),
            },
        )

    settings = get_settings()
    requirement = next(r for r in catalog if r['code'] == requirement_code)
    cap = runtime_config.max_upload_bytes()
    if requirement.get('max_size_mb'):
        cap = min(cap, int(requirement['max_size_mb']) * 1024 * 1024)
    content = _read_upload_capped(file, cap)
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

    settings.upload_path.mkdir(parents=True, exist_ok=True)

    doc = (
        db.query(Document)
        .filter(
            Document.application_id == application_id,
            Document.requirement_code == requirement_code,
        )
        .first()
    )
    req_name = next(r["name"] for r in catalog if r["code"] == requirement_code)
    if not doc:
        doc = Document(
            application_id=application_id,
            requirement_code=requirement_code,
            requirement_id=requirement.get('id'),
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
        if doc.requirement_id is None:
            doc.requirement_id = requirement.get('id')
        # Prior file versions remain on disk/DB; the slot stays the active uploaded document.
        doc.status = DocumentStatus.UPLOADED

    safe_name = result.file_name or Path(file.filename or "upload.bin").name
    # Never trust client path segments (already sanitized); keep flat storage names.
    storage_name = (
        f"{application_id}_{requirement_code}_v{version_no}_{result.sha256[:12]}_{safe_name}"
    )
    storage_path = settings.upload_path / storage_name
    # Refuse path escape if somehow present
    if ".." in storage_name or "/" in storage_name or "\\" in storage_name:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_file_name", "message": "Unsafe storage file name rejected."},
        )
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
        storage_path=storage_name,
        page_count=result.page_count,
        file_checks=checks,
        validation_outcome=(
            ValidationOutcome.WARNING if result.warnings else ValidationOutcome.PASS
        ),
        uploaded_by_id=user.id,
    )
    db.add(version)
    db.flush()

    # A replacement makes every earlier verification result describe an older file. Keep that
    # history, but stop presenting it as the current state until the new version is re-checked.
    had_verification = version_no > 1 and _retire_previous_results(db, doc, version_no)

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
    pipeline_warnings: list[str] = []

    version = db.query(DocumentVersion).filter(DocumentVersion.id == version.id).one()
    doc = db.query(Document).filter(Document.id == doc.id).one()

    if runtime_config.auto_extract_on_upload():
        try:
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
            failed_like = {
                ExtractionRunStatus.FAILED.value,
                ExtractionRunStatus.UNSUPPORTED.value,
                ExtractionRunStatus.OCR_UNAVAILABLE.value,
                ExtractionRunStatus.REQUIRES_OCR.value,
                ExtractionRunStatus.REQUIRES_MANUAL_REVIEW.value,
            }
            if extraction_status in failed_like or extraction_status.endswith("failed"):
                pipeline_warnings.append(
                    f"Extraction finished with status '{extraction_status}' — file accepted, "
                    "but text/fields may be incomplete. Not treated as authenticity success."
                )
        except Exception as exc:  # noqa: BLE001 — never hide upload if extraction crashes
            db.rollback()
            pipeline_warnings.append(
                f"Extraction failed after upload: {exc.__class__.__name__}. "
                "Document version is preserved; re-run extraction from the application page."
            )
            extraction_status = "failed"

    app = db.query(Application).filter(Application.id == application_id).first()
    try:
        val_run = run_validation(db, app, triggered_by=user.id, actor_name=user.name)
        validation_run_id = val_run.id
        if (val_run.status.value if hasattr(val_run.status, "value") else str(val_run.status)) == "failed":
            pipeline_warnings.append("Validation run reported failed status.")
    except Exception as exc:  # noqa: BLE001
        pipeline_warnings.append(
            f"Validation pipeline error after upload: {exc.__class__.__name__}. "
            "Do not treat the application as compliant."
        )

    if had_verification:
        # Dependent checks ran against the previous file; run them again on this version.
        try:
            from app.verification_engine.pipeline import run_for_document

            run_for_document(
                db, doc, triggered_by=user, validation_run_id=validation_run_id, commit=True
            )
        except Exception as exc:  # noqa: BLE001 — the upload itself already succeeded
            db.rollback()
            pipeline_warnings.append(
                f"Re-verification could not run ({exc.__class__.__name__}). "
                "Earlier results are marked out of date and will be re-checked."
            )

    if extraction_run_id and validation_run_id:
        from app.models.extraction import ExtractionRun

        ext = db.query(ExtractionRun).filter(ExtractionRun.id == extraction_run_id).first()
        if ext:
            ext.validation_run_id = validation_run_id
            db.add(ext)
            db.commit()

    if runtime_config.auto_extract_on_upload():
        try:
            from app.models.extraction import ExtractionRun as _Run
            from app.services.applicant_findings_service import processing_info

            run_row = (
                db.query(_Run).filter(_Run.id == extraction_run_id).first() if extraction_run_id else None
            )
            state, message = (
                processing_info(run_row) if run_row is not None else ("failed", "Automatic reading failed. Your file was saved.")
            )
            _notify_processing(db, app, req_name, version_no, state, message)
            db.commit()
        except Exception:  # noqa: BLE001 — a notification problem must never fail an upload
            db.rollback()

    findings_out = []
    if validation_run_id:
        findings_db = db.query(Finding).filter(Finding.validation_run_id == validation_run_id).all()
        for f in findings_db:
            _ = f.evidence
        findings_out = [finding_to_out(f) for f in findings_db]

    pipeline_ok = len(pipeline_warnings) == 0 and checks.get("ok") is True

    from app.models.extraction import ExtractionRun
    from app.services.document_check_service import build_document_check

    latest_run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_version_id == version.id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )
    document_check = build_document_check(
        requirement_name=req_name, run=latest_run, file_checks=checks
    )

    return UploadResultOut(
        document_check=document_check,
        document_version=version_no,
        replaced_previous=version_no > 1,
        document_id=doc.id,
        validation_run_id=validation_run_id,
        extraction_run_id=extraction_run_id,
        extraction_status=extraction_status,
        findings=findings_out,
        file_checks=checks,
        pipeline_ok=pipeline_ok,
        pipeline_warnings=pipeline_warnings,
    )
