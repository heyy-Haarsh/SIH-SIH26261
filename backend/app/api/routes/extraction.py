from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.extraction import (
    ExtractionFieldOut,
    ExtractionRunOut,
    ExtractionStartIn,
    FieldCorrectionIn,
    OcrCapabilityOut,
)
from app.services import extraction_service

router = APIRouter(tags=["extraction"])


def _field_out(ef, document_id: str) -> ExtractionFieldOut:
    bbox = None
    if ef.bbox_x0 is not None:
        bbox = {
            "x0": ef.bbox_x0,
            "y0": ef.bbox_y0 or 0.0,
            "x1": ef.bbox_x1 or ef.bbox_x0,
            "y1": ef.bbox_y1 or ef.bbox_y0 or 0.0,
        }
    return ExtractionFieldOut(
        id=ef.id,
        field_name=ef.field_name,
        value=ef.corrected_value or ef.value,
        raw_value=ef.raw_value or ef.value,
        normalized_value=ef.normalized_value,
        confidence=ef.confidence,
        ocr_confidence=ef.ocr_confidence,
        page_number=ef.page_number,
        page_reference=ef.page_reference,
        bbox=bbox,
        coordinate_space=ef.coordinate_space,
        method=ef.method.value if hasattr(ef.method, "value") else str(ef.method),
        review_status=ef.review_status.value if hasattr(ef.review_status, "value") else str(ef.review_status),
        corrected_value=ef.corrected_value,
        is_conflict=bool(ef.is_conflict),
        candidate_values=list(ef.candidate_values or []),
        unit=ef.unit,
        source_document_id=document_id,
        source_document_version_id=ef.document_version_id,
    )


def _run_out(run, fields=None, document_id: str = "") -> ExtractionRunOut:
    return ExtractionRunOut(
        id=run.id,
        document_version_id=run.document_version_id,
        application_id=run.application_id,
        validation_run_id=run.validation_run_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        content_kind=run.content_kind.value if hasattr(run.content_kind, "value") else str(run.content_kind),
        selected_category=run.selected_category,
        predicted_category=(
            run.predicted_category.value
            if hasattr(run.predicted_category, "value")
            else str(run.predicted_category)
        ),
        category_confidence=run.category_confidence,
        category_method=run.category_method,
        category_signals=run.category_signals or {},
        category_mismatch=bool(run.category_mismatch),
        engine_version=run.engine_version,
        page_count=run.page_count,
        pages_with_text=run.pages_with_text,
        pages_ocr=run.pages_ocr,
        warnings=list(run.warnings or []),
        error_code=run.error_code,
        error_message=run.error_message,
        stage_timings_ms=run.stage_timings_ms or {},
        ocr_available=bool(run.ocr_available),
        ocr_languages=run.ocr_languages,
        created_at=run.created_at,
        completed_at=run.completed_at,
        fields=fields or [],
    )


@router.get("/extraction/ocr-capability", response_model=OcrCapabilityOut)
def ocr_capability(_: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN))):
    return OcrCapabilityOut(**extraction_service.ocr_capability())


@router.post("/documents/{document_id}/extraction-runs", response_model=ExtractionRunOut)
def start_extraction(
    document_id: str,
    body: ExtractionStartIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    opts = body or ExtractionStartIn()
    run = extraction_service.start_extraction(
        db,
        user,
        document_id,
        force=opts.force,
        run_validation_after=opts.run_validation_after,
    )
    fields = [
        _field_out(f, document_id) for f in extraction_service.list_fields_for_run(db, run.id)
    ]
    return _run_out(run, fields, document_id)


@router.get("/documents/{document_id}/extraction-runs/latest", response_model=ExtractionRunOut | None)
def latest_extraction(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    run = extraction_service.get_latest_extraction_for_document(db, user, document_id)
    if not run:
        return None
    fields = [
        _field_out(f, document_id) for f in extraction_service.list_fields_for_run(db, run.id)
    ]
    return _run_out(run, fields, document_id)


@router.get("/extraction-runs/{run_id}", response_model=ExtractionRunOut)
def get_extraction_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    run = extraction_service.get_extraction_run(db, user, run_id)
    # Resolve document id via version
    from app.models.document import DocumentVersion

    ver = db.query(DocumentVersion).filter(DocumentVersion.id == run.document_version_id).first()
    document_id = ver.document_id if ver else ""
    fields = [
        _field_out(f, document_id) for f in extraction_service.list_fields_for_run(db, run.id)
    ]
    return _run_out(run, fields, document_id)


@router.get("/extraction-runs/{run_id}/fields", response_model=list[ExtractionFieldOut])
def list_extraction_fields(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    run = extraction_service.get_extraction_run(db, user, run_id)
    from app.models.document import DocumentVersion

    ver = db.query(DocumentVersion).filter(DocumentVersion.id == run.document_version_id).first()
    document_id = ver.document_id if ver else ""
    return [_field_out(f, document_id) for f in extraction_service.list_fields_for_run(db, run.id)]


@router.post("/extracted-fields/{field_id}/corrections", response_model=ExtractionFieldOut)
def correct_extracted_field(
    field_id: str,
    body: FieldCorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    ef = extraction_service.correct_field(db, user, field_id, corrected_value=body.corrected_value)
    from app.models.document import DocumentVersion

    ver = db.query(DocumentVersion).filter(DocumentVersion.id == ef.document_version_id).first()
    document_id = ver.document_id if ver else ""
    return _field_out(ef, document_id)
