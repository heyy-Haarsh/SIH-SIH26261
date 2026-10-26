"""Common three-layer execution pipeline driven by document-type configs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.base import utcnow
from app.models.doc_verification import DocumentVerificationCheck, DocumentVerificationRun
from app.models.document import Document, ExtractedField
from app.models.enums import (
    DocumentReviewStatus,
    DocumentVerificationRunStatus,
    ExternalVerificationLayerStatus,
    RuleValidationStatus,
    VerificationCheckLayer,
    VerificationSource,
    VerificationStatus,
)
from app.models.user import User
from app.services.audit_service import record_audit
from app.verification_engine.adapters.registry import get_adapter
from app.verification_engine.adapters.types import AdapterContext
from app.verification_engine.layer1 import evaluate_layer1
from app.verification_engine.loader import get_config_for_requirement


def _fields_for_version(db: Session, version_id: str) -> dict[str, str]:
    rows = (
        db.query(ExtractedField)
        .filter(ExtractedField.document_version_id == version_id)
        .order_by(ExtractedField.created_at.desc())
        .all()
    )
    out: dict[str, str] = {}
    for r in rows:
        key = r.field_name
        if key in out:
            continue
        val = (r.corrected_value or r.normalized_value or r.value or "").strip()
        if val:
            out[key] = val
    return out


def _map_rule_status(raw: str) -> RuleValidationStatus:
    try:
        return RuleValidationStatus(raw)
    except ValueError:
        return RuleValidationStatus.ERROR


def _aggregate_external(statuses: list[VerificationStatus]) -> ExternalVerificationLayerStatus:
    if not statuses:
        return ExternalVerificationLayerStatus.NOT_APPLICABLE
    priority = [
        VerificationStatus.MISMATCH_DETECTED,
        VerificationStatus.EXPIRED,
        VerificationStatus.SOURCE_UNAVAILABLE,
        VerificationStatus.MANUAL_REVIEW_REQUIRED,
        VerificationStatus.SIMULATED_RESULT,
        VerificationStatus.VERIFICATION_PENDING,
        VerificationStatus.VERIFIED_BY_SOURCE,
    ]
    for p in priority:
        if p in statuses:
            if p == VerificationStatus.MISMATCH_DETECTED:
                return ExternalVerificationLayerStatus.MISMATCH_DETECTED
            if p == VerificationStatus.EXPIRED:
                return ExternalVerificationLayerStatus.MISMATCH_DETECTED
            if p == VerificationStatus.SOURCE_UNAVAILABLE:
                # If any other definitive result exists alongside unavailable, mark partial
                if any(
                    s
                    in (
                        VerificationStatus.VERIFIED_BY_SOURCE,
                        VerificationStatus.MISMATCH_DETECTED,
                        VerificationStatus.SIMULATED_RESULT,
                    )
                    for s in statuses
                ):
                    return ExternalVerificationLayerStatus.PARTIAL
                return ExternalVerificationLayerStatus.SOURCE_UNAVAILABLE
            if p == VerificationStatus.MANUAL_REVIEW_REQUIRED:
                return ExternalVerificationLayerStatus.MANUAL_VERIFICATION_REQUIRED
            if p == VerificationStatus.SIMULATED_RESULT:
                return ExternalVerificationLayerStatus.SIMULATED_RESULT
            if p == VerificationStatus.VERIFICATION_PENDING:
                return ExternalVerificationLayerStatus.PENDING
            if p == VerificationStatus.VERIFIED_BY_SOURCE:
                return ExternalVerificationLayerStatus.VERIFIED_BY_SOURCE
    return ExternalVerificationLayerStatus.PARTIAL


def _needs_review(
    config: dict[str, Any],
    rule_status: RuleValidationStatus,
    ext_status: ExternalVerificationLayerStatus,
    layer2_flags: set[str],
) -> bool:
    triggers = set((config.get("layer3") or {}).get("require_review_when") or [])
    if "rule_fail" in triggers and rule_status in (
        RuleValidationStatus.FAIL,
        RuleValidationStatus.UNREADABLE,
        RuleValidationStatus.ERROR,
    ):
        return True
    if "external_unavailable" in triggers and ext_status in (
        ExternalVerificationLayerStatus.SOURCE_UNAVAILABLE,
        ExternalVerificationLayerStatus.PARTIAL,
    ):
        return True
    if "external_simulated" in triggers and ext_status == ExternalVerificationLayerStatus.SIMULATED_RESULT:
        return True
    if "expired" in triggers and "expired" in layer2_flags:
        return True
    if "signature_invalid" in triggers and "signature_invalid" in layer2_flags:
        return True
    if "coordinate_mismatch" in triggers and "coordinate_mismatch" in layer2_flags:
        return True
    if rule_status == RuleValidationStatus.MANUAL_REVIEW:
        return True
    if ext_status == ExternalVerificationLayerStatus.MANUAL_VERIFICATION_REQUIRED:
        return True
    if ext_status == ExternalVerificationLayerStatus.MISMATCH_DETECTED:
        return True
    return False


def _build_scrutiny_report(
    *,
    config: dict[str, Any],
    doc: Document,
    rule_status: RuleValidationStatus,
    ext_status: ExternalVerificationLayerStatus,
    review_status: DocumentReviewStatus,
    checks: list[DocumentVerificationCheck],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "documentId": doc.id,
        "requirementCode": doc.requirement_code,
        "configCode": config.get("code"),
        "configVersion": config.get("version"),
        "isSyntheticRules": bool(config.get("is_synthetic_rules", True)),
        "handbookNote": config.get("handbook_note"),
        "disclaimer": (
            "Passing Layer 1 (rules) never automatically establishes authenticity. "
            "External results distinguish source-confirmed, simulated, and unavailable."
        ),
        "statuses": {
            "ruleValidationStatus": rule_status.value,
            "externalVerificationStatus": ext_status.value,
            "reviewStatus": review_status.value,
        },
        "checkCounts": {
            "total": len(checks),
            "open": sum(1 for c in checks if c.status == "open"),
            "layer1": sum(1 for c in checks if c.layer == VerificationCheckLayer.RULES),
            "layer2": sum(1 for c in checks if c.layer == VerificationCheckLayer.EXTERNAL),
        },
        "limitations": limitations,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def run_for_document(
    db: Session,
    document: Document,
    *,
    triggered_by: User | None = None,
    validation_run_id: str | None = None,
    commit: bool = True,
) -> DocumentVerificationRun | None:
    config = get_config_for_requirement(document.requirement_code)
    if not config:
        return None

    version = document.latest_version
    if not version:
        document.rule_validation_status = RuleValidationStatus.SKIPPED
        document.external_verification_status = ExternalVerificationLayerStatus.NOT_APPLICABLE
        document.review_status = DocumentReviewStatus.NOT_REQUIRED
        if commit:
            db.commit()
        return None

    fields = _fields_for_version(db, version.id)
    unreadable = False
    # Heuristic: file checks failed hard, or zero fields for configs that require some
    checks_ok = (version.file_checks or {}).get("ok", True)
    if checks_ok is False:
        unreadable = True
    required = (config.get("layer1") or {}).get("required_fields") or []
    if required and not fields and (version.page_count or 0) == 0:
        unreadable = True

    run = DocumentVerificationRun(
        application_id=document.application_id,
        document_id=document.id,
        document_version_id=version.id,
        validation_run_id=validation_run_id,
        config_code=str(config.get("code")),
        config_version=str(config.get("version") or "v1"),
        status=DocumentVerificationRunStatus.RUNNING,
        triggered_by_id=triggered_by.id if triggered_by else None,
        summary={},
        limitations=[],
        scrutiny_report={},
    )
    db.add(run)
    db.flush()

    limitations: list[str] = []
    check_rows: list[DocumentVerificationCheck] = []

    # ---- Layer 1 ----
    l1 = evaluate_layer1(config, fields, unreadable=unreadable)
    rule_status = _map_rule_status(l1.status)
    limitations.extend(l1.limitations)
    for c in l1.checks:
        row = DocumentVerificationCheck(
            run_id=run.id,
            application_id=document.application_id,
            document_id=document.id,
            layer=VerificationCheckLayer.RULES,
            check_code=c.check_code,
            title=c.title,
            detail=c.detail,
            outcome=c.outcome,
            severity=c.severity,
            source=VerificationSource.LOCAL_VALIDATION,
            adapter="layer1_config_rules",
            is_synthetic_rule=bool(config.get("is_synthetic_rules", True)),
            evidence=c.evidence,
            limitations=c.limitations,
            status="open" if c.outcome not in ("pass",) else "accepted",
        )
        db.add(row)
        check_rows.append(row)

    # ---- Layer 2 ----
    file_path = version.storage_path
    if file_path and not Path(file_path).is_absolute():
        from app.core.config import settings

        candidate = settings.upload_path / file_path
        if candidate.exists():
            file_path = str(candidate)

    adapter_ctx = AdapterContext(
        document_id=document.id,
        document_version_id=version.id,
        requirement_code=document.requirement_code,
        file_path=file_path,
        mime_type=version.mime_type or "",
        fields=fields,
        subject={"sha256": version.sha256, "file_name": version.file_name},
    )
    layer2_statuses: list[VerificationStatus] = []
    layer2_flags: set[str] = set()
    partial_failure = False

    for spec in (config.get("layer2") or {}).get("adapters") or []:
        adapter_id = spec.get("id")
        if not adapter_id:
            continue
        fn = get_adapter(adapter_id)
        if not fn:
            partial_failure = True
            row = DocumentVerificationCheck(
                run_id=run.id,
                application_id=document.application_id,
                document_id=document.id,
                layer=VerificationCheckLayer.EXTERNAL,
                check_code=f"ADAPTER_MISSING_{adapter_id}",
                title=f"Adapter not registered: {adapter_id}",
                detail="Configured adapter id has no implementation.",
                outcome=VerificationStatus.SOURCE_UNAVAILABLE.value,
                severity="warning",
                source=VerificationSource.AUTHORIZED_LIVE,
                adapter=adapter_id,
                is_synthetic_rule=False,
                evidence={},
                limitations=["Missing adapter implementation"],
                status="open",
            )
            db.add(row)
            check_rows.append(row)
            layer2_statuses.append(VerificationStatus.SOURCE_UNAVAILABLE)
            continue
        try:
            result = fn(adapter_ctx)
        except Exception as exc:  # noqa: BLE001 — partial failure must not mark Layer 1 pass as authentic
            partial_failure = True
            result_status = VerificationStatus.SOURCE_UNAVAILABLE
            row = DocumentVerificationCheck(
                run_id=run.id,
                application_id=document.application_id,
                document_id=document.id,
                layer=VerificationCheckLayer.EXTERNAL,
                check_code=f"ADAPTER_ERROR_{adapter_id}",
                title=f"Adapter error: {adapter_id}",
                detail=f"Adapter raised: {exc}",
                outcome=result_status.value,
                severity="warning",
                source=VerificationSource.AUTHORIZED_LIVE,
                adapter=adapter_id,
                is_synthetic_rule=False,
                evidence={},
                limitations=["Adapter exception"],
                status="open",
            )
            db.add(row)
            check_rows.append(row)
            layer2_statuses.append(result_status)
            continue

        layer2_statuses.append(result.status)
        if result.status == VerificationStatus.MISMATCH_DETECTED:
            if "signature" in (result.claim_type or ""):
                layer2_flags.add("signature_invalid")
            if "coordinate" in (result.claim_type or ""):
                layer2_flags.add("coordinate_mismatch")
        if "expired" in (result.detail or "").lower():
            layer2_flags.add("expired")
        if result.evidence.get("flag") == "expired":
            layer2_flags.add("expired")

        row = DocumentVerificationCheck(
            run_id=run.id,
            application_id=document.application_id,
            document_id=document.id,
            layer=VerificationCheckLayer.EXTERNAL,
            check_code=f"{adapter_id}:{result.claim_type}",
            title=f"Layer 2 · {adapter_id}",
            detail=result.detail,
            outcome=result.status.value,
            severity=(
                "failed"
                if result.status == VerificationStatus.MISMATCH_DETECTED
                else "warning"
                if result.status
                in (
                    VerificationStatus.SOURCE_UNAVAILABLE,
                    VerificationStatus.MANUAL_REVIEW_REQUIRED,
                    VerificationStatus.SIMULATED_RESULT,
                )
                else "info"
            ),
            source=result.source,
            adapter=result.adapter,
            is_synthetic_rule=False,
            evidence=result.evidence,
            limitations=result.limitations,
            status="open"
            if result.status
            not in (VerificationStatus.VERIFIED_BY_SOURCE,)
            else "accepted",
        )
        db.add(row)
        check_rows.append(row)
        limitations.extend(result.limitations)

    ext_status = _aggregate_external(layer2_statuses)
    if partial_failure and ext_status == ExternalVerificationLayerStatus.VERIFIED_BY_SOURCE:
        # Never allow partial adapter failure to look fully verified
        ext_status = ExternalVerificationLayerStatus.PARTIAL

    # Also fold Layer 1 expired field flags
    for c in l1.checks:
        if c.evidence.get("flag") == "expired":
            layer2_flags.add("expired")

    # ---- Layer 3 ----
    needs = _needs_review(config, rule_status, ext_status, layer2_flags)
    review_status = DocumentReviewStatus.PENDING if needs else DocumentReviewStatus.NOT_REQUIRED
    if needs:
        db.add(
            DocumentVerificationCheck(
                run_id=run.id,
                application_id=document.application_id,
                document_id=document.id,
                layer=VerificationCheckLayer.REVIEW,
                check_code="REVIEW_REQUIRED",
                title="Officer review required",
                detail=(
                    "Automated layers produced signals requiring human review. "
                    "Rule pass does not establish authenticity."
                ),
                outcome="pending",
                severity="manual_review",
                source=VerificationSource.MANUAL_REVIEWER,
                adapter="layer3_review",
                is_synthetic_rule=False,
                evidence={
                    "ruleValidationStatus": rule_status.value,
                    "externalVerificationStatus": ext_status.value,
                },
                limitations=[],
                status="open",
            )
        )

    # Deduplicate limitations
    uniq_lim: list[str] = []
    for lim in limitations:
        if lim and lim not in uniq_lim:
            uniq_lim.append(lim)
    uniq_lim.append("Passing rule checks must never automatically establish authenticity.")

    db.flush()
    # Refresh check list from session
    checks = (
        db.query(DocumentVerificationCheck)
        .filter(DocumentVerificationCheck.run_id == run.id)
        .all()
    )
    report = _build_scrutiny_report(
        config=config,
        doc=document,
        rule_status=rule_status,
        ext_status=ext_status,
        review_status=review_status,
        checks=checks,
        limitations=uniq_lim,
    )

    run.rule_validation_status = rule_status
    run.external_verification_status = ext_status
    run.review_status = review_status
    run.limitations = uniq_lim
    run.scrutiny_report = report
    run.summary = {
        "fieldCount": len(fields),
        "adapterCount": len((config.get("layer2") or {}).get("adapters") or []),
        "partialFailure": partial_failure,
        "configPath": config.get("_config_path"),
    }
    run.status = (
        DocumentVerificationRunStatus.COMPLETED_PARTIAL
        if partial_failure
        else DocumentVerificationRunStatus.COMPLETED
    )
    run.completed_at = utcnow()

    document.rule_validation_status = rule_status
    document.external_verification_status = ext_status
    document.review_status = review_status
    document.latest_verification_run_id = run.id

    record_audit(
        db,
        action="doc_verification.completed",
        actor=triggered_by.name if triggered_by else "system",
        actor_id=triggered_by.id if triggered_by else None,
        actor_role=triggered_by.role.value if triggered_by else "system",
        detail=(
            f"doc={document.id}; req={document.requirement_code}; "
            f"L1={rule_status.value}; L2={ext_status.value}; L3={review_status.value}"
        ),
        application_id=document.application_id,
        entity_type="document_verification_run",
        entity_id=run.id,
    )

    if commit:
        db.commit()
        db.refresh(run)
    return run


def run_for_application(
    db: Session,
    application: Application,
    *,
    triggered_by: User | None = None,
    validation_run_id: str | None = None,
    commit: bool = True,
) -> list[DocumentVerificationRun]:
    runs: list[DocumentVerificationRun] = []
    docs = (
        db.query(Document)
        .filter(Document.application_id == application.id)
        .all()
    )
    for doc in docs:
        run = run_for_document(
            db,
            doc,
            triggered_by=triggered_by,
            validation_run_id=validation_run_id,
            commit=False,
        )
        if run:
            runs.append(run)
    if commit:
        db.commit()
        for r in runs:
            db.refresh(r)
    return runs
