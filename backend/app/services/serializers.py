from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.document import Document
from app.models.enums import FindingSeverity
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.validation import Finding
from app.models.verification import VerificationRequest
from app.schemas.common import (
    ApplicationDetailOut,
    ApplicationSummaryOut,
    AuditEventOut,
    DocumentOut,
    DocumentRequirementOut,
    EvidenceOut,
    ExtractedFieldOut,
    FindingOut,
    ReviewNoteOut,
    VerificationOut,
)
from app.core.seed import DEFAULT_DOCS


def _enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


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


def application_summary(db: Session, app: Application) -> ApplicationSummaryOut:
    deficiency_count = (
        db.query(DeficiencyNotice).filter(DeficiencyNotice.application_id == app.id).count()
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
        assigned_officer=officer_name,
    )


def document_to_out(doc: Document) -> DocumentOut:
    version = doc.latest_version
    outcome = "pending"
    if version is not None:
        outcome = _enum_val(version.validation_outcome)
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
                extracted.append(
                    ExtractedFieldOut(
                        id=ef.id,
                        field_name=ef.field_name,
                        value=ef.value,
                        confidence=ef.confidence,
                        page_reference=ef.page_reference,
                        source_document_id=doc.id,
                        source_document_name=version.file_name,
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
    return ApplicationDetailOut(
        **summary.model_dump(),
        academic_year=app.academic_year,
        program_name=app.program_name,
        contact_email=app.contact_email,
        requirements=requirements,
        documents=[document_to_out(d) for d in app.documents],
        extracted_fields=extracted,
        findings=[finding_to_out(f) for f in findings],
        discrepancies=[],
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
