from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.document import Document
from app.models.enums import FindingSeverity
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.validation import Finding
from app.models.verification import VerificationRequest
from app.models.enums import DeficiencyStatus
from app.schemas.common import (
    ApplicationDetailOut,
    ApplicationSummaryOut,
    AuditEventOut,
    DeficiencyOut,
    DiscrepancyOut,
    DocumentOut,
    DocumentRequirementOut,
    EvidenceOut,
    ExtractedFieldOut,
    FindingOut,
    ForensicsEvidenceOut,
    ForensicsIndicatorOut,
    ForensicsRunOut,
    ReconciliationRunOut,
    ReconciliationValueOut,
    ReviewNoteOut,
    VerificationOut,
)
from app.core.seed import DEFAULT_DOCS
from app.services import forensics_service, reconciliation_service


def _enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def reconciliation_value_to_out(v) -> ReconciliationValueOut:
    return ReconciliationValueOut(
        document_id=v.document_id,
        document_name=v.document_name,
        value=v.value,
        normalized_value=v.normalized_value,
        page=v.page_reference,
        page_number=v.page_number,
        extracted_field_id=v.extracted_field_id,
        evidence_snippet=v.evidence_snippet,
    )


def reconciliation_item_to_out(item) -> DiscrepancyOut:
    return DiscrepancyOut(
        id=item.id,
        field_name=item.field_name,
        outcome=_enum_val(item.outcome),
        values=[reconciliation_value_to_out(v) for v in item.values],
        severity=_enum_val(item.severity),
        status=_enum_val(item.status),
        title=item.title,
        description=item.description,
        match_kind=item.match_kind,
        original_outcome=_enum_val(item.original_outcome),
        resolution_reason=item.resolution_reason,
        resolved_at=item.resolved_at,
        fingerprint=item.fingerprint,
    )


def reconciliation_run_to_out(run) -> ReconciliationRunOut:
    return ReconciliationRunOut(
        id=run.id,
        application_id=run.application_id,
        validation_run_id=run.validation_run_id,
        status=_enum_val(run.status),
        trigger=run.trigger,
        engine_version=run.engine_version,
        input_fingerprint=run.input_fingerprint,
        summary=run.summary or {},
        items=[reconciliation_item_to_out(i) for i in (run.items or [])],
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def forensics_evidence_to_out(e) -> ForensicsEvidenceOut:
    return ForensicsEvidenceOut(
        id=e.id,
        description=e.description,
        document_id=e.document_id,
        document_name=e.document_name,
        page_number=e.page_number,
        page_reference=e.page_reference,
        detail=e.detail,
    )


def forensics_indicator_to_out(item) -> ForensicsIndicatorOut:
    return ForensicsIndicatorOut(
        id=item.id,
        document_id=item.document_id,
        code=_enum_val(item.code),
        risk_class=_enum_val(item.risk_class),
        original_risk_class=_enum_val(item.original_risk_class),
        severity=_enum_val(item.severity),
        status=_enum_val(item.status),
        verification_status=_enum_val(item.verification_status),
        title=item.title,
        description=item.description,
        affected_pages=list(item.affected_pages or []),
        evidence=[forensics_evidence_to_out(e) for e in item.evidence],
        metadata=dict(item.indicator_metadata or {}),
        resolution_reason=item.resolution_reason,
        resolved_at=item.resolved_at,
        fingerprint=item.fingerprint,
    )


def forensics_run_to_out(run) -> ForensicsRunOut:
    return ForensicsRunOut(
        id=run.id,
        application_id=run.application_id,
        validation_run_id=run.validation_run_id,
        status=_enum_val(run.status),
        trigger=run.trigger,
        engine_version=run.engine_version,
        input_fingerprint=run.input_fingerprint,
        summary=run.summary or {},
        limitations=list(run.limitations or []),
        indicators=[forensics_indicator_to_out(i) for i in (run.indicators or [])],
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def finding_to_out(f: Finding) -> FindingOut:
    return FindingOut(
        id=f.id,
        title=f.title,
        description=f.description,
        severity=_enum_val(f.severity),
        status=_enum_val(f.status),
        outcome=_enum_val(f.outcome),
        rule_id=f.rule_code,
        rule_name=f.rule_name,
        rule_version=f.rule_version,
        handbook_ref=f.handbook_ref,
        evidence=[
            EvidenceOut(
                id=e.id,
                description=e.description,
                document_id=e.document_id,
                document_name=e.document_name,
                page_reference=e.page_reference,
                rule_id=e.rule_code,
                rule_version=e.rule_version,
            )
            for e in f.evidence
        ],
        created_at=f.created_at,
    )


def deficiency_to_out(n: DeficiencyNotice, application_number: str | None = None) -> DeficiencyOut:
    return DeficiencyOut(
        id=n.id,
        application_id=n.application_id,
        application_number=application_number,
        title=n.title,
        description=n.description,
        status=_enum_val(n.status),
        finding_id=n.finding_id,
        due_date=n.due_date,
        applicant_response=n.applicant_response,
        responded_at=n.responded_at,
        created_at=n.created_at,
        resolved_at=n.resolved_at,
    )


def application_summary(db: Session, app: Application) -> ApplicationSummaryOut:
    deficiency_count = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == app.id,
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
        )
        .count()
    )
    officer_name = app.assigned_officer.name if app.assigned_officer else None
    return ApplicationSummaryOut(
        id=app.id,
        application_number=app.application_number,
        institution_id=app.institution_id,
        institution_name=app.institution.name if app.institution else "",
        category=app.category.name if app.category else "",
        category_code=app.category.code if app.category else "",
        submitted_at=app.submitted_at,
        status=_enum_val(app.status),
        priority=_enum_val(app.priority),
        deficiency_count=deficiency_count,
        finding_count=app.finding_count,
        requires_manual_review=app.requires_manual_review,
        priority_score=app.priority_score,
        score_config_version=app.score_config_version,
        assigned_officer=officer_name,
    )


def document_to_out(doc: Document, db: Session | None = None) -> DocumentOut:
    version = doc.latest_version
    outcome = "pending"
    extraction_status = None
    content_kind = None
    predicted = None
    selected = doc.requirement_code
    mismatch = False
    run_id = None
    if version is not None:
        outcome = _enum_val(version.validation_outcome)
        if db is not None:
            from app.models.extraction import ExtractionRun

            run = (
                db.query(ExtractionRun)
                .filter(ExtractionRun.document_version_id == version.id)
                .order_by(ExtractionRun.created_at.desc())
                .first()
            )
            if run:
                extraction_status = _enum_val(run.status)
                content_kind = _enum_val(run.content_kind)
                predicted = _enum_val(run.predicted_category)
                selected = run.selected_category or doc.requirement_code
                mismatch = bool(run.category_mismatch)
                run_id = run.id
    return DocumentOut(
        id=doc.id,
        name=doc.name,
        requirement_code=doc.requirement_code,
        file_name=version.file_name if version else doc.name,
        mime_type=version.mime_type if version else "application/octet-stream",
        size_bytes=version.size_bytes if version else 0,
        uploaded_at=version.uploaded_at if version else doc.created_at,
        version=doc.current_version,
        status=outcome,
        page_count=version.page_count if version else None,
        extraction_status=extraction_status,
        content_kind=content_kind,
        predicted_category=predicted,
        selected_category=selected,
        category_mismatch=mismatch,
        latest_extraction_run_id=run_id,
        rule_validation_status=_enum_val(getattr(doc, "rule_validation_status", None))
        if getattr(doc, "rule_validation_status", None) is not None
        else "pending",
        external_verification_status=_enum_val(getattr(doc, "external_verification_status", None))
        if getattr(doc, "external_verification_status", None) is not None
        else "pending",
        review_status=_enum_val(getattr(doc, "review_status", None))
        if getattr(doc, "review_status", None) is not None
        else "pending",
        latest_verification_run_id=getattr(doc, "latest_verification_run_id", None),
    )


def application_detail(db: Session, app: Application) -> ApplicationDetailOut:
    req_defs = app.category.required_documents if app.category else DEFAULT_DOCS
    uploaded = {d.requirement_code for d in app.documents}
    requirements = [
        DocumentRequirementOut(
            id=f"req-{r['code']}",
            code=r["code"],
            name=r["name"],
            mandatory=bool(r.get("mandatory", True)),
            status="uploaded" if r["code"] in uploaded else "missing",
            allowed_types=list(r.get("allowed_types") or ["pdf"]),
        )
        for r in req_defs
    ]

    extracted: list[ExtractedFieldOut] = []
    for doc in app.documents:
        for version in doc.versions:
            for ef in version.extracted_fields:
                bbox = None
                if ef.bbox_x0 is not None and ef.bbox_y0 is not None:
                    bbox = {
                        "x0": ef.bbox_x0,
                        "y0": ef.bbox_y0,
                        "x1": ef.bbox_x1 or ef.bbox_x0,
                        "y1": ef.bbox_y1 or ef.bbox_y0,
                    }
                extracted.append(
                    ExtractedFieldOut(
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
                        method=_enum_val(ef.method) if ef.method else None,
                        review_status=_enum_val(ef.review_status) if ef.review_status else None,
                        is_conflict=bool(ef.is_conflict),
                        candidate_values=list(ef.candidate_values or []),
                        unit=ef.unit,
                        source_document_id=doc.id,
                        source_document_name=version.file_name,
                        extraction_run_id=ef.extraction_run_id,
                        corrected_value=ef.corrected_value,
                    )
                )

    findings = (
        db.query(Finding)
        .filter(Finding.application_id == app.id)
        .order_by(Finding.created_at.desc())
        .all()
    )
    for f in findings:
        _ = f.evidence

    from app.models.validation import ValidationRun

    latest_run = (
        db.query(ValidationRun)
        .filter(ValidationRun.application_id == app.id)
        .order_by(ValidationRun.created_at.desc())
        .first()
    )

    verifications = (
        db.query(VerificationRequest).filter(VerificationRequest.application_id == app.id).all()
    )
    reviews = db.query(ReviewDecision).filter(ReviewDecision.application_id == app.id).all()
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.application_id == app.id)
        .order_by(AuditEvent.created_at.desc())
        .all()
    )

    summary = application_summary(db, app)
    latest_forensics = forensics_service.get_latest_run(db, app.id)
    deficiencies = (
        db.query(DeficiencyNotice)
        .filter(DeficiencyNotice.application_id == app.id)
        .order_by(DeficiencyNotice.created_at.desc())
        .all()
    )
    from app.models.doc_verification import DocumentVerificationRun
    from app.services import doc_verification_service as doc_verif_svc

    # Latest run per document (Phase 7)
    doc_runs_q = (
        db.query(DocumentVerificationRun)
        .filter(DocumentVerificationRun.application_id == app.id)
        .order_by(DocumentVerificationRun.created_at.desc())
        .all()
    )
    latest_by_doc: dict[str, DocumentVerificationRun] = {}
    for r in doc_runs_q:
        if r.document_id not in latest_by_doc:
            latest_by_doc[r.document_id] = r
    # Ensure checks are loaded
    doc_verif_out = []
    for r in latest_by_doc.values():
        full = (
            db.query(DocumentVerificationRun)
            .filter(DocumentVerificationRun.id == r.id)
            .first()
        )
        if full:
            # lazy-load checks
            _ = full.checks
            doc_verif_out.append(doc_verif_svc.run_to_dict(full))

    return ApplicationDetailOut(
        **summary.model_dump(),
        academic_year=app.academic_year,
        program_name=app.program_name,
        contact_email=app.contact_email,
        requirements=requirements,
        documents=[document_to_out(d, db) for d in app.documents],
        extracted_fields=extracted,
        findings=[finding_to_out(f) for f in findings],
        discrepancies=[
            reconciliation_item_to_out(i)
            for i in reconciliation_service.list_open_items_for_application(db, app.id)
        ],
        forensics_indicators=[
            forensics_indicator_to_out(i)
            for i in forensics_service.list_open_indicators(db, app.id)
        ],
        forensics_limitations=list((latest_forensics.limitations or []) if latest_forensics else []),
        deficiencies=[deficiency_to_out(n, app.application_number) for n in deficiencies],
        score_breakdown=dict(app.score_breakdown or {}),
        scrutiny_summary=dict(app.scrutiny_summary or {}),
        last_transition_at=app.last_transition_at,
        last_transition_note=app.last_transition_note,
        document_verification_runs=doc_verif_out,
        verifications=[
            VerificationOut(
                id=v.id,
                claim=v.claim,
                status=_enum_val(v.status),
                source=_enum_val(v.source),
                detail=v.detail,
                checked_at=v.checked_at,
            )
            for v in verifications
        ],
        review_notes=[
            ReviewNoteOut(
                id=r.id,
                author=r.author.name if r.author else r.author_id,
                role=_enum_val(r.author_role),
                content=r.content,
                created_at=r.created_at,
            )
            for r in reviews
        ],
        audit_events=[
            AuditEventOut(
                id=a.id,
                action=a.action,
                actor=a.actor_name,
                timestamp=a.created_at,
                detail=a.detail,
            )
            for a in audits
        ],
        validation_run_id=latest_run.id if latest_run else None,
        validation_run_status=_enum_val(latest_run.status) if latest_run else None,
    )


def count_failed_findings(findings: list[Finding]) -> int:
    return sum(1 for f in findings if f.severity == FindingSeverity.FAILED)
