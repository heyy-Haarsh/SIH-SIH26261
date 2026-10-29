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
from app.services import findings_service, forensics_service, reconciliation_service
from app.services.document_check_service import build_document_check
from app.services.status_model import STAGE_LABELS, stage_of


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


def _open_issue_count(db: Session, app: Application) -> int:
    # Imported lazily: the review service itself imports serializers.
    from app.services.scrutiny_view_service import open_issue_count

    return open_issue_count(db, app)


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
        institution_name=(app.institution_name or (app.institution.name if app.institution else "")),
        category=app.category.name if app.category else "",
        category_code=app.category.code if app.category else "",
        submitted_at=app.submitted_at,
        status=_enum_val(app.status),
        priority=_enum_val(app.priority),
        deficiency_count=deficiency_count,
        finding_count=_open_issue_count(db, app),
        stage=stage_of(app.status),
        stage_label=STAGE_LABELS[stage_of(app.status)],
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
    check = None
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
            check = build_document_check(
                requirement_name=doc.name, run=run, file_checks=version.file_checks
            )
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
        document_check=check,
    )


def extracted_field_to_out(ef, doc: Document, file_name: str) -> ExtractedFieldOut:
    bbox = None
    if ef.bbox_x0 is not None and ef.bbox_y0 is not None:
        bbox = {
            "x0": ef.bbox_x0,
            "y0": ef.bbox_y0,
            "x1": ef.bbox_x1 or ef.bbox_x0,
            "y1": ef.bbox_y1 or ef.bbox_y0,
        }
    return ExtractedFieldOut(
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
        source_document_name=file_name,
        extraction_run_id=ef.extraction_run_id,
        corrected_value=ef.corrected_value,
    )


def current_extracted_fields(doc: Document) -> list[ExtractedFieldOut]:
    """Fields of the document's *current* version and its latest extraction run only.

    Superseded versions and older extraction runs are history; showing them next to the current
    values is what made replaced documents look like they still had the old data.
    """
    version = doc.latest_version
    if version is None:
        return []
    fields = list(version.extracted_fields)
    run_ids = [(f.extraction_run_id, f.created_at) for f in fields if f.extraction_run_id]
    if run_ids:
        latest_run = max(run_ids, key=lambda t: t[1])[0]
        fields = [f for f in fields if f.extraction_run_id in (latest_run, None)]
    return [extracted_field_to_out(f, doc, version.file_name) for f in fields]


def application_detail(db: Session, app: Application) -> ApplicationDetailOut:
    from app.services import category_config_service

    req_defs = category_config_service.effective_requirements(app)
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
        extracted.extend(current_extracted_fields(doc))

    # Only the latest completed run's findings are "current"; earlier runs stay in the database
    # as history and are never shown next to (or counted with) the current result.
    findings = list(reversed(findings_service.current_findings(db, app.id)))
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
        db.query(VerificationRequest)
        .filter(
            VerificationRequest.application_id == app.id,
            VerificationRequest.validation_run_id == (latest_run.id if latest_run else None),
        )
        .all()
        if latest_run
        else []
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


# --- Phase 1 engine DTOs (app.schemas.engine) ---------------------------------

_LAYER2_TO_ENGINE_STATUS = {
    "verified_by_source": "verified",
    "verified": "verified",
    "mismatch_detected": "mismatch_detected",
    "expired": "expired",
    "verification_pending": "verification_pending",
    "pending": "verification_pending",
    "source_unavailable": "source_unavailable",
    "manual_verification_required": "manual_review_required",
    "manual_review_required": "manual_review_required",
    "simulated_result": "source_unavailable",
    "not_applicable": "source_unavailable",
    "partial": "manual_review_required",
    "error": "source_unavailable",
}


def _map_external_status(raw: str):
    from app.schemas.engine import ExternalVerificationStatus

    key = (raw or "").strip().lower()
    mapped = _LAYER2_TO_ENGINE_STATUS.get(key, "source_unavailable")
    return ExternalVerificationStatus(mapped)


def to_document_result_out(run) -> "DocumentResultOut":  # noqa: F821
    """Map a DocumentVerificationRun ORM row to the Phase 1 engine DTO."""
    from datetime import datetime, timezone

    from app.schemas.engine import (
        DocumentResultOut,
        EvidenceOut as EngineEvidenceOut,
        FindingOut as EngineFindingOut,
        VerificationMode,
        VerificationResultOut,
    )

    ext_raw = (
        run.external_verification_status.value
        if hasattr(run.external_verification_status, "value")
        else str(run.external_verification_status)
    )
    rule_raw = (
        run.rule_validation_status.value
        if hasattr(run.rule_validation_status, "value")
        else str(run.rule_validation_status)
    )
    review_raw = (
        run.review_status.value if hasattr(run.review_status, "value") else str(run.review_status)
    )
    summary = run.summary or {}
    signature_status = str(summary.get("signature_status") or "not_applicable")

    findings: list = []
    verification_results: list = []
    for check in run.checks or []:
        layer = check.layer.value if hasattr(check.layer, "value") else str(check.layer)
        ev = [
            EngineEvidenceOut(
                document_id=run.document_id,
                snippet=(check.detail or "")[:240],
                source=check.source.value if hasattr(check.source, "value") else str(check.source),
            )
        ]
        findings.append(
            EngineFindingOut(
                id=check.id,
                rule_id=check.check_code,
                severity=check.severity or "info",
                message=check.title or check.detail or check.check_code,
                evidence=ev,
                clause_ref="TODO: fill from handbook",
            )
        )
        if "layer2" in layer or layer.endswith("external"):
            src = check.source.value if hasattr(check.source, "value") else str(check.source)
            mode = (
                VerificationMode.SIMULATED
                if src == "simulated_dev" or (check.outcome or "").lower() == "simulated_result"
                else VerificationMode.REAL
            )
            verification_results.append(
                VerificationResultOut(
                    status=_map_external_status(check.outcome or ext_raw),
                    mode=mode,
                    official_verification=False,
                    provider_name=check.check_code,
                    provider_reference_id=None,
                    timestamp=check.created_at or datetime.now(timezone.utc),
                    request_summary=f"check={check.check_code}",
                    response_summary=check.detail or check.outcome,
                    scope_of_confirmation="adapter outcome only — not document authenticity",
                )
            )

    if not verification_results:
        from datetime import datetime, timezone

        verification_results.append(
            VerificationResultOut(
                status=_map_external_status(ext_raw),
                mode=VerificationMode.REAL,
                official_verification=False,
                provider_name="pipeline",
                timestamp=run.completed_at or run.created_at or datetime.now(timezone.utc),
                request_summary="document verification run",
                response_summary=ext_raw,
                scope_of_confirmation="layer status aggregate — not document authenticity",
            )
        )

    return DocumentResultOut(
        document_id=run.document_id,
        requirement_code=run.config_code,
        document_type=run.config_code,
        rule_validation_status=rule_raw,
        external_verification_status=_map_external_status(ext_raw),
        review_status=review_raw,
        signature_status=signature_status,
        findings=findings,
        forensic_signals=[],
        verification_results=verification_results,
        official_source_confirmed=False,
    )


def to_application_result_out(
    *,
    application_id: str,
    runs: list,
    rule_set_version: str = "v1",
    engine_version: str = "praman-engine-0.1",
    overall_status: str = "manual_review_required",
) -> "ApplicationResultOut":  # noqa: F821
    from datetime import datetime, timezone

    from app.schemas.engine import ApplicationResultOut, TriageScoreOut

    docs = [to_document_result_out(r) for r in runs]
    unconfirmed = [d.requirement_code for d in docs if not d.official_source_confirmed]
    if unconfirmed:
        disclaimer = (
            "IMPORTANT: The following documents were NOT confirmed by any official "
            f"external source: {', '.join(unconfirmed)}. "
            "All simulated results are marked [SIMULATED] and have official_verification=false. "
            "Decision-support output; final decision rests with the competent authority."
        )
    else:
        disclaimer = (
            "All documents were verified against official sources. "
            "Decision-support output; final decision rests with the competent authority."
        )
    return ApplicationResultOut(
        application_id=application_id,
        rule_set_version=rule_set_version,
        engine_version=engine_version,
        generated_at=datetime.now(timezone.utc),
        documents=docs,
        cross_doc_findings=[],
        triage_score_breakdown=TriageScoreOut(total=0.0, signals=[], config_version="triage-v0"),
        overall_status=overall_status,
        report_disclaimer=disclaimer,
    )
