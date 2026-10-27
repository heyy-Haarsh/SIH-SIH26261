"""Per-document verification report: the full pipeline for one uploaded document.

Stages (never merged, because a pass in one proves nothing about the next):
  1 Intake & clarity  ->  2 OCR & classification  ->  3 Layer 1 rules
  ->  4 Layer 2 verification & reconciliation  ->  5 Layer 3 evidence & officer review
"""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFoundError
from app.document_processing.ocr_processor import tesseract_status
from app.models.application import Application
from app.models.document import Document
from app.models.enums import (
    ForensicsIndicatorStatus,
    ReconciliationItemStatus,
    ReconciliationOutcome,
)
from app.models.extraction import ExtractionRun
from app.models.forensics import ForensicsIndicator
from app.models.reconciliation import ReconciliationItem
from app.models.validation import Finding
from app.schemas.scrutiny import (
    DocumentReportOut,
    DocumentVersionBriefOut,
    PipelineCheckOut,
    PipelineDetailOut,
    PipelineStageOut,
)
from app.services import issue_text, serializers
from app.services.document_check_service import build_document_check
from app.services.scrutiny_view_service import (
    COUNTED,
    DISCLAIMER,
    PASS_OUTCOMES,
    ReviewContext,
    collect_issues,
    document_card,
    enum_val,
    norm_severity,
)

_EXTERNAL_STAGE_STATUS = {
    "verified_by_source": "pass",
    "mismatch_detected": "failed",
    "source_unavailable": "unavailable",
    "manual_verification_required": "manual_review",
    "simulated_result": "warning",
    "partial": "warning",
    "error": "unavailable",
    "pending": "not_run",
    "not_applicable": "not_run",
}


def _worst(statuses: list[str]) -> str:
    order = ["failed", "manual_review", "warning", "unavailable", "pass", "not_run"]
    for s in order:
        if s in statuses:
            return s
    return "not_run"


def _finding_check(ctx: ReviewContext, f: Finding) -> PipelineCheckOut:
    text = issue_text.describe_finding(f.rule_code, f.title, f.description, ctx.doc_name(f.document_id))
    sev = norm_severity(enum_val(f.severity))
    st = enum_val(f.status)
    return PipelineCheckOut(
        id=f.id,
        title=text.title,
        outcome=enum_val(f.outcome),
        severity=sev,
        status=st,
        detail=text.explanation,
        source="rule engine",
        resolvable=(st == "open" and sev in COUNTED),
        resolve_kind="finding",
        handbook=ctx.handbook.lookup(f.rule_code),
    )


def _intake_stage(doc: Document, v, check, extra: list[PipelineCheckOut]) -> PipelineStageOut:
    fc = v.file_checks or {}
    warnings = list(fc.get("warnings") or [])
    errors = list(fc.get("errors") or [])
    status = "failed" if errors or fc.get("ok") is False else ("warning" if warnings else "pass")
    if check.clarity == "unreadable":
        status = "failed"
    elif check.clarity == "unclear" and status == "pass":
        status = "warning"
    if any(c.status == "open" and c.severity in ("failed",) for c in extra):
        status = "failed" if status == "pass" else status
    checks = [
        PipelineCheckOut(
            id=f"intake-w{n}",
            title="File advisory",
            outcome="warning",
            severity="warning",
            detail=w,
            status="open",
            source="local validation",
        )
        for n, w in enumerate(warnings)
    ]
    checks += [
        PipelineCheckOut(
            id=f"intake-e{n}",
            title="File rejected",
            outcome="fail",
            severity="failed",
            detail=e,
            status="open",
            source="local validation",
        )
        for n, e in enumerate(errors)
    ]
    checks += extra
    return PipelineStageOut(
        key="intake",
        title="1 · Intake & clarity",
        status=status,
        summary=check.clarity_message,
        details=[
            PipelineDetailOut(label="File", value=v.file_name),
            PipelineDetailOut(label="Type", value=f"{v.mime_type} (.{v.extension})"),
            PipelineDetailOut(label="Size", value=f"{v.size_bytes:,} bytes"),
            PipelineDetailOut(label="Pages", value=str(v.page_count) if v.page_count else "n/a"),
            PipelineDetailOut(label="SHA-256", value=v.sha256[:16] + "…"),
            PipelineDetailOut(label="Version", value=f"v{doc.current_version}"),
        ],
        checks=checks,
    )


def _classification_stage(
    run: ExtractionRun | None, check, extra: list[PipelineCheckOut]
) -> PipelineStageOut:
    if run is None:
        return PipelineStageOut(
            key="classification",
            title="2 · OCR & classification",
            status="not_run",
            summary="Text extraction has not run for this file yet.",
        )
    st = enum_val(run.status)
    ocr = tesseract_status()
    ocr_text = (
        f"available ({'+'.join(ocr.get('languages_usable') or [])})"
        if ocr.get("available")
        else "not available on this server"
    )
    details = [
        PipelineDetailOut(label="Extraction status", value=st.replace("_", " ")),
        PipelineDetailOut(label="Content kind", value=enum_val(run.content_kind).replace("_", " ")),
        PipelineDetailOut(
            label="Pages with text / OCR'd",
            value=f"{run.pages_with_text or 0} / {run.pages_ocr or 0} of {run.page_count or '?'}",
        ),
        PipelineDetailOut(label="OCR engine", value=ocr_text),
        PipelineDetailOut(label="OCR languages configured", value=run.ocr_languages or "eng"),
        PipelineDetailOut(label="Expected document", value=check.expected_type),
        PipelineDetailOut(
            label="Detected as",
            value=(
                f"{check.detected_type}"
                + (
                    f" ({run.category_confidence:.0%} confidence, {run.category_method})"
                    if run.category_confidence is not None
                    else ""
                )
                if check.detected_type
                else "could not be determined"
            ),
        ),
        PipelineDetailOut(label="Type match", value=check.type_match_message),
    ]
    if check.language_note:
        details.append(PipelineDetailOut(label="Language", value=check.language_note))
    checks = [
        PipelineCheckOut(
            id=f"ext-w{n}",
            title="Extraction note",
            outcome="warning",
            severity="warning",
            detail=str(w),
            status="open",
            source="extraction",
        )
        for n, w in enumerate(run.warnings or [])
    ]
    if run.error_message:
        checks.append(
            PipelineCheckOut(
                id="ext-error",
                title="Extraction error",
                outcome="fail",
                severity="failed",
                detail=run.error_message,
                status="open",
                source="extraction",
            )
        )
    checks += extra
    if st in ("failed", "unsupported") or check.clarity == "unreadable":
        status = "failed"
    elif st in ("ocr_unavailable", "requires_ocr"):
        status = "unavailable"
    elif check.type_match == "mismatch" or st == "requires_manual_review":
        status = "manual_review"
    elif st == "completed_with_warnings" or check.type_match == "unclear" or check.clarity == "unclear":
        status = "warning"
    else:
        status = "pass"
    return PipelineStageOut(
        key="classification",
        title="2 · OCR & classification",
        status=status,
        summary=check.type_match_message,
        details=details,
        checks=checks,
    )


def _current_after(item, uploaded_at) -> bool:
    """Open items are live; a *resolved* item that predates the current file describes an old file."""
    st = enum_val(item.status)
    if st == "open":
        return True
    return item.created_at >= uploaded_at


def build_document_report(db: Session, app: Application, document_id: str) -> DocumentReportOut:
    doc = (
        db.query(Document)
        .options(joinedload(Document.versions))
        .filter(Document.id == document_id, Document.application_id == app.id)
        .first()
    )
    if doc is None or doc.latest_version is None:
        raise NotFoundError("Document not found.")
    v = doc.latest_version
    ctx = ReviewContext(db, app)
    issues = collect_issues(ctx)
    ext_run = ctx.extraction_runs.get(doc.id)
    check = build_document_check(requirement_name=doc.name, run=ext_run, file_checks=v.file_checks)
    card = document_card(ctx, doc, issues)
    vrun = ctx.verif_runs.get(doc.id)

    my_findings = [f for f in ctx.findings if f.document_id == doc.id and f.rule_code != "SYN-RULE-008"]
    by_layer: dict[str, list[PipelineCheckOut]] = {"intake": [], "classification": [], "layer1": []}
    for f in my_findings:
        text = issue_text.describe_finding(f.rule_code, f.title, f.description, doc.name)
        if text.layer in by_layer:
            by_layer[text.layer].append(_finding_check(ctx, f))

    stages: list[PipelineStageOut] = [
        _intake_stage(doc, v, check, by_layer["intake"]),
        _classification_stage(ext_run, check, by_layer["classification"]),
    ]

    # ---- Layer 1 -------------------------------------------------------------------
    l1_checks = list(by_layer["layer1"])
    l1_limits: list[str] = []
    cfg_note = ""
    if vrun:
        for c in vrun.checks:
            if enum_val(c.layer) == "layer1_rules":
                l1_checks.append(_check_out(ctx, vrun, c))
        cfg_note = f"Config {vrun.config_code} v{vrun.config_version}" + (
            " (synthetic demo rules)" if any(c.is_synthetic_rule for c in vrun.checks) else ""
        )
        status_l1 = {
            "pass": "pass",
            "warning": "warning",
            "fail": "failed",
            "manual_review": "manual_review",
            "unreadable": "failed",
            "error": "unavailable",
            "skipped": "not_run",
            "pending": "not_run",
        }.get(enum_val(vrun.rule_validation_status), "not_run")
        l1_limits = [x for x in (vrun.limitations or []) if "Layer 1" in x or "rule" in x.lower()][:3]
    else:
        status_l1 = "not_run"
    finding_status = _worst(
        [
            "failed" if c.severity == "failed" and c.status == "open" else
            "manual_review" if c.severity == "manual_review" and c.status == "open" else
            "warning" if c.severity == "warning" and c.status == "open" else "pass"
            for c in by_layer["layer1"]
        ]
    )
    if status_l1 == "not_run" and by_layer["layer1"]:
        status_l1 = finding_status
    elif status_l1 in ("pass", "warning") and finding_status in ("failed", "manual_review"):
        status_l1 = finding_status
    l1_summary = (
        "Required fields, formats and dates checked against the document-type rules. "
        "A pass here is not proof the document is genuine."
        if vrun
        else "No document-type rule set exists for this requirement; only the general rule engine ran."
    )
    stages.append(
        PipelineStageOut(
            key="layer1",
            title="3 · Layer 1 — rules",
            status=status_l1,
            summary=l1_summary,
            details=[PipelineDetailOut(label="Rule set", value=cfg_note or "general rule engine only")],
            checks=l1_checks,
            limitations=l1_limits,
        )
    )

    # ---- Layer 2 -------------------------------------------------------------------
    l2_checks: list[PipelineCheckOut] = []
    l2_status_parts: list[str] = []
    l2_limits: list[str] = []
    if vrun:
        for c in vrun.checks:
            if enum_val(c.layer) == "layer2_external":
                l2_checks.append(_check_out(ctx, vrun, c))
                l2_limits.extend(x for x in (c.limitations or []) if x not in l2_limits)
        l2_status_parts.append(
            _EXTERNAL_STAGE_STATUS.get(enum_val(vrun.external_verification_status), "not_run")
        )
    items = (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.values))
        .filter(
            ReconciliationItem.application_id == app.id,
            ReconciliationItem.status != ReconciliationItemStatus.CLEARED,
        )
        .order_by(ReconciliationItem.created_at.desc())
        .all()
    )
    for it in items:
        if not any(val.document_id == doc.id for val in it.values):
            continue
        if not _current_after(it, v.uploaded_at):
            continue
        is_match = it.outcome == ReconciliationOutcome.MATCH
        st = enum_val(it.status)
        vals = "; ".join(f"{val.document_name}: “{val.value}”" for val in it.values)
        l2_checks.append(
            PipelineCheckOut(
                id=it.id,
                title=f"Cross-document: {it.title}",
                outcome=enum_val(it.outcome),
                severity="info" if is_match else norm_severity(enum_val(it.severity)),
                status="passed" if is_match else st,
                detail=(issue_text.clean(it.description) + (f" Values — {vals}" if vals else "")).strip(),
                source="reconciliation",
                resolution_reason=it.resolution_reason,
                resolvable=(not is_match and st == "open"),
                resolve_kind="reconciliation",
            )
        )
        if not is_match and st == "open":
            l2_status_parts.append("failed" if enum_val(it.severity) == "failed" else "manual_review")
        elif is_match:
            l2_status_parts.append("pass")
    if not vrun and not l2_checks:
        l2_status = "not_run"
    else:
        l2_status = _worst(l2_status_parts or ["not_run"])
        if l2_status == "pass" and vrun and enum_val(vrun.external_verification_status) != "verified_by_source":
            l2_status = _EXTERNAL_STAGE_STATUS.get(enum_val(vrun.external_verification_status), "pass")
    stages.append(
        PipelineStageOut(
            key="layer2",
            title="4 · Layer 2 — verification & reconciliation",
            status=l2_status,
            summary=(
                "Checks against external/local sources and against the other uploaded documents. "
                "Simulated or unavailable sources are labelled and never count as verified."
            ),
            checks=l2_checks,
            limitations=l2_limits[:6],
        )
    )

    # ---- Layer 3 -------------------------------------------------------------------
    indicators = (
        db.query(ForensicsIndicator)
        .options(joinedload(ForensicsIndicator.evidence))
        .filter(
            ForensicsIndicator.application_id == app.id,
            ForensicsIndicator.document_id == doc.id,
            ForensicsIndicator.status != ForensicsIndicatorStatus.CLEARED,
        )
        .order_by(ForensicsIndicator.created_at.desc())
        .all()
    )
    l3_checks: list[PipelineCheckOut] = []
    l3_parts: list[str] = []
    for ind in indicators:
        if not _current_after(ind, v.uploaded_at):
            continue
        risk = enum_val(ind.risk_class)
        st = enum_val(ind.status)
        serious = risk in ("authenticity_concern", "possible_duplicate", "technical_anomaly")
        l3_checks.append(
            PipelineCheckOut(
                id=ind.id,
                title=issue_text.clean(ind.title),
                outcome=risk,
                severity=norm_severity(enum_val(ind.severity)),
                status=st,
                detail=issue_text.clean(ind.description),
                source="forensics",
                resolution_reason=ind.resolution_reason,
                resolvable=(st == "open" and serious),
                resolve_kind="forensics",
            )
        )
        if st == "open" and risk in ("authenticity_concern", "possible_duplicate"):
            l3_parts.append("manual_review")
        elif st == "open" and risk == "technical_anomaly":
            l3_parts.append("warning")
        elif st == "open" and risk == "check_limitation":
            l3_parts.append("unavailable")
    review = enum_val(doc.review_status)
    if review in ("pending", "in_review"):
        l3_parts.append("manual_review")
    elif review == "not_required" and vrun:
        l3_parts.append("pass")
    elif review in ("resolved", "waived", "accepted"):
        l3_parts.append("pass")
    l3_status = _worst(l3_parts or ["not_run"])
    stages.append(
        PipelineStageOut(
            key="layer3",
            title="5 · Layer 3 — evidence & officer review",
            status=l3_status,
            summary=(
                "Authenticity / tamper-risk signals and the officer's review. A clean result means "
                "no signal was detected — it is not a statement that the document is authentic."
            ),
            details=[PipelineDetailOut(label="Review status", value=review.replace("_", " "))],
            checks=l3_checks,
        )
    )

    versions = [
        DocumentVersionBriefOut(
            version=ver.version,
            file_name=ver.file_name,
            uploaded_at=ver.uploaded_at,
            size_bytes=ver.size_bytes,
            sha256=ver.sha256,
            is_current=ver.id == v.id,
        )
        for ver in sorted(doc.versions, key=lambda x: x.version, reverse=True)
    ]
    return DocumentReportOut(
        document=card,
        stages=stages,
        issues=[i for i in issues if i.document_id == doc.id],
        extracted_fields=serializers.current_extracted_fields(doc),
        versions=versions,
        disclaimer=DISCLAIMER,
    )


def _check_out(ctx: ReviewContext, run, c) -> PipelineCheckOut:
    layer = enum_val(c.layer)
    passed = c.outcome in PASS_OUTCOMES
    src = enum_val(c.source)
    mode = None
    if layer == "layer2_external":
        if c.outcome == "verified_by_source" and src == "authorized_live":
            mode = "real"
        elif src == "simulated_dev" or c.outcome == "simulated_result":
            mode = "simulated"
        elif c.outcome == "source_unavailable":
            mode = "unavailable"
        else:
            mode = "local"
    return PipelineCheckOut(
        id=c.id,
        title=issue_text.clean(c.title),
        outcome=c.outcome,
        severity=norm_severity(c.severity),
        status="passed" if passed else c.status,
        detail=issue_text.clean(c.detail),
        source=src.replace("_", " "),
        mode=mode,
        limitations=list(c.limitations or []),
        resolution_reason=c.resolution_reason,
        resolvable=(not passed and c.status == "open" and layer != "layer3_review"),
        resolve_kind="check",
        handbook=(
            ctx.handbook.lookup(f"{run.config_code}:{c.check_code}", run.config_code)
            if layer == "layer1_rules"
            else None
        ),
    )
