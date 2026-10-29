"""Which findings are *current*, and how resolutions carry across validation runs.

Every validation run writes a fresh set of findings and keeps the old ones as history.
Everything that shows or scores "the issues" must therefore look at the latest completed run only —
otherwise a corrected document keeps showing the old problem next to the new result.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session, joinedload

from app.models.document import Document
from app.models.enums import FindingStatus, ValidationRunStatus
from app.models.validation import Finding, ValidationRun


def latest_completed_run(db: Session, application_id: str) -> ValidationRun | None:
    db.flush()  # sessions run with autoflush off; make a just-completed run visible
    return (
        db.query(ValidationRun)
        .filter(
            ValidationRun.application_id == application_id,
            ValidationRun.status == ValidationRunStatus.COMPLETED,
        )
        .order_by(ValidationRun.created_at.desc())
        .first()
    )


def current_findings(db: Session, application_id: str, *, with_evidence: bool = False) -> list[Finding]:
    """Findings produced by the latest completed validation run (empty if none)."""
    run = latest_completed_run(db, application_id)
    if run is None:
        return []
    q = db.query(Finding).filter(
        Finding.application_id == application_id, Finding.validation_run_id == run.id
    )
    if with_evidence:
        q = q.options(joinedload(Finding.evidence))
    return q.order_by(Finding.created_at.asc()).all()


def historical_finding_count(db: Session, application_id: str) -> int:
    """Findings from earlier runs, kept for audit/history but not shown as current issues."""
    run = latest_completed_run(db, application_id)
    q = db.query(Finding).filter(Finding.application_id == application_id)
    if run is not None:
        q = q.filter(Finding.validation_run_id != run.id)
    return q.count()


def finding_fingerprint(
    *,
    rule_code: str | None,
    document_id: str | None,
    title: str,
    description: str,
    versions_key: str = "",
) -> str:
    raw = "|".join([rule_code or "", document_id or "", title.strip(), description.strip(), versions_key])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def versions_key_for(db: Session, application_id: str, document_ids: set[str]) -> str:
    """Stable key of the *current versions* of the documents a finding is about."""
    if not document_ids:
        return ""
    docs = (
        db.query(Document)
        .filter(Document.application_id == application_id, Document.id.in_(list(document_ids)))
        .all()
    )
    return ",".join(sorted(f"{d.id}:{d.current_version}" for d in docs))


def prior_resolutions(db: Session, application_id: str) -> dict[str, tuple[FindingStatus, Finding]]:
    """fingerprint -> (latest non-open status, finding) from all earlier runs.

    The most recent finding for a fingerprint decides: if the officer reopened or it was open
    last time, it is not carried forward.
    """
    rows = (
        db.query(Finding)
        .filter(Finding.application_id == application_id, Finding.fingerprint != "")
        .order_by(Finding.created_at.asc())
        .all()
    )
    latest: dict[str, Finding] = {}
    for f in rows:
        latest[f.fingerprint] = f
    # Carry forward every deliberate officer state; open and system-retired superseded start fresh.
    return {
        fp: (f.status, f)
        for fp, f in latest.items()
        if f.status not in (FindingStatus.OPEN, FindingStatus.SUPERSEDED)
    }
