from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.document_processing.aggregator import FindingAggregator
from app.document_processing.classifier import NameBasedClassifier
from app.document_processing.extraction import BasicNormalizationModule, LocalExtractionModule
from app.document_processing.forensics import UnavailableForensicsModule
from app.document_processing.reconciliation import BasicReconciliationModule
from app.document_processing.types import (
    EvalContext,
    EvalDocument,
    FieldRecord,
    FileWarning,
    ModuleResult,
)
from app.integrations.base import VerificationClaim, VerificationSource, VerificationStatus
from app.integrations.registry import get_verification_adapter
from app.models.application import Application
from app.models.document import Document
from app.models.enums import FindingStatus, ValidationRunStatus
from app.models.base import utcnow
from app.models.validation import Finding, FindingEvidence, ValidationRun
from app.models.verification import VerificationRequest
from app.rules.engine import ENGINE_VERSION, RULESET_VERSION, RuleEngine
from app.services.audit_service import record_audit
from app.core.seed import DEFAULT_DOCS


def _persist_finding(db: Session, application_id: str, run_id: str, draft) -> Finding:
    finding = Finding(
        application_id=application_id,
        validation_run_id=run_id,
        document_id=draft.document_id,
        title=draft.title,
        description=draft.description,
        severity=draft.severity,
        status=FindingStatus.OPEN,
        outcome=draft.outcome,
        rule_code=draft.rule_code,
        rule_name=draft.rule_name,
        rule_version=draft.rule_version,
        handbook_ref=draft.handbook_ref,
    )
    db.add(finding)
    db.flush()
    for ev in draft.evidence:
        db.add(
            FindingEvidence(
                finding_id=finding.id,
                description=ev.description,
                document_id=ev.document_id,
                document_name=ev.document_name,
                page_reference=ev.page_reference,
                rule_code=draft.rule_code,
                rule_version=draft.rule_version,
            )
        )
    return finding


def run_validation(
    db: Session,
    application: Application,
    *,
    triggered_by: str | None,
    actor_name: str,
) -> ValidationRun:
    application = (
        db.query(Application)
        .options(joinedload(Application.category), joinedload(Application.documents))
        .filter(Application.id == application.id)
        .one()
    )

    classifier = NameBasedClassifier()
    extractor = LocalExtractionModule()
    normalizer = BasicNormalizationModule()
    reconciler = BasicReconciliationModule()
    forensics = UnavailableForensicsModule()
    rules = RuleEngine()
    aggregator = FindingAggregator()

    module_results: list[ModuleResult] = [
        classifier.capability(),
        extractor.capability(),
        reconciler.capability(),
        rules.capability(),
        forensics.capability(),
        aggregator.capability(),
    ]

    docs = db.query(Document).filter(Document.application_id == application.id).all()
    eval_docs: list[EvalDocument] = []
    field_records: list[FieldRecord] = []

    for d in docs:
        _ = d.versions
        version = d.latest_version
        if not version:
            continue
        content = b""
        path = Path(version.storage_path)
        if path.exists():
            content = path.read_bytes()

        classification = classifier.classify(file_name=version.file_name)
        drafts = extractor.extract(
            file_name=version.file_name, extension=version.extension, content=content
        )
        drafts = normalizer.normalize(drafts)
        fields = {f.field_name: f.value for f in drafts}
        for f in drafts:
            field_records.append(
                FieldRecord(
                    field_name=f.field_name,
                    value=f.value,
                    document_id=d.id,
                    document_name=version.file_name,
                    page_reference=f.page_reference,
                )
            )

        warnings = []
        for w in (version.file_checks or {}).get("warnings", []):
            warnings.append(FileWarning(code="file_advisory", message=str(w)))

        eval_docs.append(
            EvalDocument(
                document_id=d.id,
                requirement_code=d.requirement_code,
                requirement_name=d.name,
                file_name=version.file_name,
                extension=version.extension,
                mime_type=version.mime_type,
                declared_content_type=version.declared_content_type,
                size_bytes=version.size_bytes,
                sha256=version.sha256,
                warnings=warnings,
                fields=fields,
                classification=classification,
            )
        )
        forensics.analyze(file_name=version.file_name, content=content)

    discrepancies = reconciler.reconcile(field_records)
    requirements = (
        application.category.required_documents if application.category else DEFAULT_DOCS
    )

    ctx = EvalContext(
        category_code=application.category.code if application.category else "",
        program_name=application.program_name,
        academic_year=application.academic_year,
        requirements=requirements,
        documents=eval_docs,
        discrepancies=discrepancies,
        module_results=module_results,
        today=date.today(),
    )

    now = datetime.now(timezone.utc)
    run = ValidationRun(
        application_id=application.id,
        status=ValidationRunStatus.RUNNING,
        trigger="api",
        triggered_by_id=triggered_by,
        engine_version=ENGINE_VERSION,
        rule_set_version=RULESET_VERSION,
        started_at=now,
        summary={},
    )
    db.add(run)
    db.flush()

    drafts = rules.evaluate(ctx)
    aggregation = aggregator.aggregate(drafts, module_results)

    for draft in aggregation.findings:
        _persist_finding(db, application.id, run.id, draft)

    adapter = get_verification_adapter()
    outcome = adapter.verify(
        VerificationClaim(
            claim_type="document_authenticity",
            claim="Issuing-authority document authenticity",
        )
    )
    db.add(
        VerificationRequest(
            application_id=application.id,
            validation_run_id=run.id,
            claim_type="document_authenticity",
            claim="Issuing-authority document authenticity",
            status=outcome.status,
            source=outcome.source,
            adapter=outcome.adapter,
            detail=outcome.detail,
            checked_at=outcome.checked_at,
        )
    )
    all_ok = all(
        (d.latest_version.file_checks or {}).get("ok", True)
        for d in docs
        if d.latest_version
    )
    db.add(
        VerificationRequest(
            application_id=application.id,
            validation_run_id=run.id,
            claim_type="file_integrity",
            claim="File integrity (hash / basic pre-check)",
            status=(
                VerificationStatus.VERIFIED_BY_SOURCE
                if all_ok
                else VerificationStatus.MISMATCH_DETECTED
            ),
            source=VerificationSource.LOCAL_VALIDATION,
            adapter="local_integrity",
            detail="Local file-type, size, and checksum pre-checks.",
            checked_at=utcnow(),
        )
    )

    from app.document_processing.aggregator import ReviewSupportPacketBuilder

    packet = ReviewSupportPacketBuilder().build_packet(aggregation)

    application.finding_count = len(aggregation.findings)
    application.requires_manual_review = bool(packet.get("requiresManualReview"))
    # Prioritization aid only
    score = min(
        100,
        sum(
            {"failed": 40, "manual_review": 30, "warning": 15, "info": 5}.get(
                f.severity.value, 5
            )
            for f in aggregation.findings
        ),
    )
    application.priority_score = score

    run.status = ValidationRunStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        **aggregation.summary,
        "priorityScore": score,
        "priorityScoreNote": "Prioritization aid only — not proof of fraud or compliance",
        "reviewPacket": packet,
    }

    record_audit(
        db,
        action="validation.run_completed",
        actor=actor_name,
        actor_id=triggered_by,
        detail=f"{len(aggregation.findings)} findings; priority_score={score}",
        application_id=application.id,
    )
    db.commit()
    db.refresh(run)
    return run
