"""Applicant-safe findings, clarifications and processing states.

What an institution may see is deliberately narrow:

* findings the scrutiny officer attached to a clarification request, and findings the officer
  closed with a written note — never raw automated diagnostics, scores, rule codes or forensics;
* free text only when it passes ``safe_text`` (no key=value internals, no accusatory wording);
* extracted values only through the evidence endpoint, for a finding the institution can see.

A discrepancy, unclear scan or unavailable source is described as something to check, never as
fraud or proof that a document is not genuine.
"""

from __future__ import annotations

import hashlib
import re

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.document import Document, DocumentVersion
from app.models.enums import ApplicationStatus, DeficiencyStatus, FindingStatus
from app.models.extraction import ExtractionRun
from app.models.finding_transition import DeficiencyFinding
from app.models.review import DeficiencyNotice, DeficiencyResponse
from app.models.validation import Finding
from app.schemas.common import (
    ApplicantAffectedDocumentOut,
    ApplicantDeficiencyOut,
    ApplicantFindingDocumentOut,
    ApplicantFindingOut,
    ApplicantLinkedItemOut,
    ApplicantResponseEntryOut,
)
from app.services import clarification_service

# ---------------------------------------------------------------- safe wording

_INTERNAL = re.compile(
    r"(\b\w+=\S)|\b(fingerprint|rule[_ ]?code|signals?|confidence|score|checksum|sha256|"
    r"traceback|exception|stack|heuristic|fraud\w*|forg\w+|fake|counterfeit|tamper\w*|"
    r"fabricat\w+|suspicio\w+)\b",
    re.IGNORECASE,
)
GENERIC_EXPLANATION = (
    "The automatic check noted something the scrutiny officer needs to look at. "
    "This is not a conclusion about your documents."
)


def safe_text(text: str | None, limit: int = 400) -> str | None:
    """Return text only if it is free of internal markers and accusatory language."""
    value = (text or "").strip()
    if not value or _INTERNAL.search(value):
        return None
    return value[:limit]


# ---------------------------------------------------------------- processing state

_PROCESSING: dict[str, tuple[str, str]] = {
    "queued": ("processing", "Waiting to be checked."),
    "running": ("processing", "Being checked now."),
    "completed": ("ready", "Text was read from this file. The officer still reviews it."),
    "completed_with_warnings": (
        "limited",
        "The file was read, but some parts may be unclear. The officer will take this into account.",
    ),
    "requires_ocr": (
        "limited",
        "This looks like a scanned document, so its text could not be read automatically. "
        "A clearer or text-based PDF helps; your file was kept.",
    ),
    "ocr_unavailable": (
        "limited",
        "Scanned pages could not be read because text recognition is not available on this server. "
        "Your file was kept and the officer can still open it.",
    ),
    "unsupported": (
        "failed",
        "This file type cannot be read automatically. Your file was saved; upload a PDF or a clear image if you can.",
    ),
    "requires_manual_review": (
        "limited",
        "The file could not be read automatically and has been left for the officer to review.",
    ),
    "failed": (
        "failed",
        "Automatic reading failed. Your file was saved and nothing was lost; you can upload it again.",
    ),
}


def processing_info(run: ExtractionRun | None) -> tuple[str, str]:
    if run is None:
        return "not_run", "Not checked yet."
    status = run.status.value if hasattr(run.status, "value") else str(run.status)
    return _PROCESSING.get(status, ("limited", "Checked with limitations."))


def latest_runs_by_version(db: Session, doc: Document) -> dict[int, ExtractionRun]:
    runs = (
        db.query(ExtractionRun, DocumentVersion.version)
        .join(DocumentVersion, DocumentVersion.id == ExtractionRun.document_version_id)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(ExtractionRun.created_at)
        .all()
    )
    out: dict[int, ExtractionRun] = {}
    for run, version in runs:
        out[version] = run  # ordered by time, so the last one per version wins
    return out


# ---------------------------------------------------------------- findings

def reference_for(app: Application, finding: Finding, requirement_code: str | None) -> str:
    """Stable across validation re-runs and document versions for 'the same issue on the same slot'."""
    basis = "|".join([app.id, finding.rule_code or "", requirement_code or "", finding.title])
    return "F-" + hashlib.sha1(basis.encode()).hexdigest()[:6].upper()


def _status_value(f: Finding) -> str:
    return f.status.value if hasattr(f.status, "value") else str(f.status)


def _finding_version(db: Session, finding: Finding, doc: Document | None) -> int | None:
    if finding.extraction_run_id:
        row = (
            db.query(DocumentVersion.version)
            .join(ExtractionRun, ExtractionRun.document_version_id == DocumentVersion.id)
            .filter(ExtractionRun.id == finding.extraction_run_id)
            .first()
        )
        if row:
            return row[0]
    return doc.current_version if doc else None


def _status_for(f: Finding, notice: DeficiencyNotice | None, app_status: ApplicationStatus) -> tuple[str, str, str]:
    """(status, label, next action) in the institution's words."""
    state = _status_value(f)
    if state == FindingStatus.SUPERSEDED.value:
        return (
            "rechecked",
            "Re-checked after replacement",
            "A newer version of this document was checked. No action unless the officer writes again.",
        )
    if state in ("resolved", "waived", "accepted"):
        label = {"resolved": "Resolved", "waived": "Waived by the officer", "accepted": "Accepted by the officer"}[state]
        return state, label, "No action needed."
    if notice is not None and notice.status == DeficiencyStatus.OPEN:
        needs = "Upload the replacement document, then send your response." if notice.requires_replacement else (
            "Respond to the clarification request."
        )
        return "response_needed", "Response needed", needs
    if notice is not None and notice.status == DeficiencyStatus.RESPONDED:
        if app_status in (ApplicationStatus.CLARIFICATION_REQUIRED, ApplicationStatus.DEFICIENCY):
            return (
                "response_submitted",
                "Response saved",
                "Resubmit the application when every request is answered.",
            )
        return "response_submitted", "Awaiting officer review", "Nothing to do — the officer will review your response."
    return "open", "With the scrutiny officer", "No action needed unless the officer contacts you."


def build_findings(
    db: Session, app: Application, notices: list[DeficiencyNotice]
) -> list[ApplicantFindingOut]:
    docs = {d.id: d for d in app.documents}
    notice_by_id = {n.id: n for n in notices}

    rows: list[tuple[Finding, DeficiencyNotice | None]] = []
    if notices:
        for link, finding in (
            db.query(DeficiencyFinding, Finding)
            .join(Finding, Finding.id == DeficiencyFinding.finding_id)
            .filter(DeficiencyFinding.deficiency_id.in_(list(notice_by_id)))
            .all()
        ):
            rows.append((finding, notice_by_id[link.deficiency_id]))
    linked_ids = {f.id for f, _ in rows}
    # Closed with a written officer note (resolved / waived / accepted), even without a request.
    for finding in db.query(Finding).filter(
        Finding.application_id == app.id,
        Finding.status.in_([FindingStatus.RESOLVED, FindingStatus.WAIVED, FindingStatus.ACCEPTED]),
    ):
        if finding.id not in linked_ids and len((finding.resolution_reason or "").strip()) >= 5:
            rows.append((finding, None))

    best: dict[str, tuple[Finding, DeficiencyNotice | None]] = {}
    for finding, notice in rows:
        doc = docs.get(finding.document_id) if finding.document_id else None
        ref = reference_for(app, finding, doc.requirement_code if doc else None)
        previous = best.get(ref)
        # The most recent record of an issue wins; a superseded one only shows if it is all there is.
        if previous is None or finding.created_at >= previous[0].created_at:
            best[ref] = (finding, notice if notice is not None else (previous[1] if previous else None))

    out: list[ApplicantFindingOut] = []
    for ref, (finding, notice) in best.items():
        doc = docs.get(finding.document_id) if finding.document_id else None
        version = _finding_version(db, finding, doc)
        status, label, next_action = _status_for(finding, notice, app.status)
        evidence = next(
            (e for e in finding.evidence if e.page_reference or safe_text(e.description)),
            None,
        )
        officer_note = safe_text(finding.resolution_reason, 600) if status in ("resolved", "waived", "accepted") else None
        out.append(
            ApplicantFindingOut(
                id=finding.id,
                reference=ref,
                kind="officer_request" if notice is not None else "officer_update",
                title=safe_text(finding.title, 160) or "Item for the scrutiny officer",
                explanation=safe_text(finding.description) or GENERIC_EXPLANATION,
                requested_correction=(notice.description if notice is not None else officer_note),
                document=ApplicantFindingDocumentOut(
                    document_id=doc.id if doc else None,
                    name=doc.name if doc else "Application",
                    version=version,
                    current_version=doc.current_version if doc else None,
                ),
                page_reference=evidence.page_reference if evidence else None,
                snippet=safe_text(evidence.description, 300) if evidence else None,
                status=status,
                status_label=label,
                next_action=next_action,
                clarification_id=notice.id if notice is not None else None,
                officer_note=officer_note,
                updated_at=finding.resolved_at or finding.created_at,
                outdated_version=bool(doc and version is not None and doc.current_version > version),
            )
        )
    order = {"response_needed": 0, "open": 1, "response_submitted": 2, "rechecked": 3, "resolved": 4, "waived": 4, "accepted": 4}
    out.sort(key=lambda f: (order.get(f.status, 5), f.reference))
    return out


# ---------------------------------------------------------------- clarifications

def _applicant_state(notice: DeficiencyNotice, app_status: ApplicationStatus) -> str:
    if notice.status == DeficiencyStatus.OPEN:
        return "action_required"
    if notice.status == DeficiencyStatus.RESPONDED:
        if app_status in (ApplicationStatus.CLARIFICATION_REQUIRED, ApplicationStatus.DEFICIENCY):
            return "response_saved"
        return "awaiting_review"
    return "resolved"


def build_clarifications(
    db: Session, app: Application, notices: list[DeficiencyNotice]
) -> list[ApplicantDeficiencyOut]:
    docs = {d.id: d for d in app.documents}
    ids = [n.id for n in notices]
    links: dict[str, list[Finding]] = {}
    if ids:
        for link, finding in (
            db.query(DeficiencyFinding, Finding)
            .join(Finding, Finding.id == DeficiencyFinding.finding_id)
            .filter(DeficiencyFinding.deficiency_id.in_(ids))
            .all()
        ):
            links.setdefault(link.deficiency_id, []).append(finding)
    responses: dict[str, list[DeficiencyResponse]] = {}
    if ids:
        for r in (
            db.query(DeficiencyResponse)
            .filter(DeficiencyResponse.deficiency_id.in_(ids))
            .order_by(DeficiencyResponse.created_at)
        ):
            responses.setdefault(r.deficiency_id, []).append(r)

    out: list[ApplicantDeficiencyOut] = []
    for n in notices:
        findings = links.get(n.id, [])
        seen: set[tuple[str, str]] = set()
        items: list[ApplicantLinkedItemOut] = []
        refs: list[str] = []
        for f in findings:
            doc = docs.get(f.document_id) if f.document_id else None
            name = doc.name if doc else "Application"
            if (name, f.title) not in seen:
                seen.add((name, f.title))
                items.append(
                    ApplicantLinkedItemOut(document_name=name, summary=safe_text(f.title, 160) or "Item to review")
                )
            ref = reference_for(app, f, doc.requirement_code if doc else None)
            if ref not in refs:
                refs.append(ref)
        affected = [
            ApplicantAffectedDocumentOut(
                document_id=d.id, name=d.name, current_version=d.current_version
            )
            for d in (docs.get(i) for i in clarification_service.affected_document_ids(db, n))
            if d is not None
        ]
        received = bool(clarification_service.replacements_since_request(db, n))
        out.append(
            ApplicantDeficiencyOut(
                id=n.id,
                title=n.title,
                description=n.description,
                status=n.status.value if hasattr(n.status, "value") else str(n.status),
                applicant_response=n.applicant_response,
                responded_at=n.responded_at,
                created_at=n.created_at,
                resolved_at=n.resolved_at,
                linked_items=items,
                application_id=app.id,
                application_number=app.application_number,
                requested_by=n.issued_by.name if n.issued_by is not None else None,
                due_date=n.due_date,
                requires_replacement=bool(n.requires_replacement),
                replacement_received=received,
                applicant_state=_applicant_state(n, app.status),
                affected_documents=affected,
                finding_refs=refs,
                responses=[
                    ApplicantResponseEntryOut(
                        id=r.id, mode=r.mode, text=r.text, documents=list(r.documents or []), created_at=r.created_at
                    )
                    for r in responses.get(n.id, [])
                ],
            )
        )
    order = {"action_required": 0, "response_saved": 1, "awaiting_review": 2, "resolved": 3}
    out.sort(key=lambda c: (order.get(c.applicant_state, 4), -c.created_at.timestamp()))
    return out


def finding_visible_to_applicant(db: Session, app: Application, finding: Finding) -> bool:
    """Same visibility rule as ``build_findings`` — used to authorise the evidence endpoint."""
    if finding.application_id != app.id:
        return False
    if db.query(DeficiencyFinding).filter(DeficiencyFinding.finding_id == finding.id).first():
        return True
    # A finding superseded by a re-run keeps the link only on its own row; check the same issue.
    doc = next((d for d in app.documents if d.id == finding.document_id), None)
    ref = reference_for(app, finding, doc.requirement_code if doc else None)
    for notice_link, f in (
        db.query(DeficiencyFinding, Finding)
        .join(Finding, Finding.id == DeficiencyFinding.finding_id)
        .filter(Finding.application_id == app.id)
        .all()
    ):
        d = next((x for x in app.documents if x.id == f.document_id), None)
        if reference_for(app, f, d.requirement_code if d else None) == ref:
            return True
    status = _status_value(finding)
    return status in ("resolved", "waived", "accepted") and len((finding.resolution_reason or "").strip()) >= 5
