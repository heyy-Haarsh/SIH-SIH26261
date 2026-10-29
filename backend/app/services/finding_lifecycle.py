"""Finding lifecycle: legal transitions, history records, and the supersede-on-rerun rule.

Every status change goes through ``apply_transition`` so it is validated against the edge table
and written to ``finding_transitions`` (who, when, why). Nothing here decides an application —
these are officer bookkeeping states on evidence the system surfaced.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnprocessableError
from app.models.base import utcnow
from app.models.enums import ACTIVE_FINDING_STATUSES, FindingStatus
from app.models.finding_transition import FindingTransition
from app.models.user import User
from app.models.validation import Finding

S = FindingStatus

# Edges an OFFICER may take by hand. ``superseded`` is system-only and terminal.
OFFICER_EDGES: dict[FindingStatus, frozenset[FindingStatus]] = {
    S.OPEN: frozenset({S.UNDER_REVIEW, S.CLARIFICATION_REQUESTED, S.RESOLVED, S.WAIVED, S.ACCEPTED}),
    S.UNDER_REVIEW: frozenset(
        {S.OPEN, S.CLARIFICATION_REQUESTED, S.RESOLVED, S.WAIVED, S.ACCEPTED}
    ),
    S.CLARIFICATION_REQUESTED: frozenset(
        {S.UNDER_REVIEW, S.RESOLVED, S.WAIVED, S.ACCEPTED}
    ),
    S.REOPENED: frozenset(
        {S.UNDER_REVIEW, S.CLARIFICATION_REQUESTED, S.RESOLVED, S.WAIVED, S.ACCEPTED}
    ),
    # Revising a closed decision is allowed, but it is recorded in the history like any other move.
    S.RESOLVED: frozenset({S.REOPENED, S.WAIVED, S.ACCEPTED}),
    S.WAIVED: frozenset({S.REOPENED, S.RESOLVED, S.ACCEPTED}),
    S.ACCEPTED: frozenset({S.REOPENED, S.RESOLVED, S.WAIVED}),
    S.SUPERSEDED: frozenset(),
}

# Moves that need a written reason (closing or reopening is a judgement worth explaining).
REASON_REQUIRED = frozenset({S.RESOLVED, S.WAIVED, S.ACCEPTED, S.REOPENED, S.CLARIFICATION_REQUESTED})

CLOSING = frozenset({S.RESOLVED, S.WAIVED, S.ACCEPTED})


def _val(status: FindingStatus | str) -> str:
    return status.value if hasattr(status, "value") else str(status)


def apply_transition(
    db: Session,
    finding: Finding,
    to: FindingStatus,
    *,
    actor: User | None,
    reason: str = "",
    system: bool = False,
    reason_label: str | None = None,
) -> FindingTransition:
    """Validate and perform one transition; returns the history row (not committed).

    ``system=True`` bypasses the officer edge table (used for supersede and applicant-response
    moves) but still records the change.
    """
    current = FindingStatus(_val(finding.status))
    reason = (reason or "").strip()
    renote = current == to and to in CLOSING  # same closing decision with an updated note
    if current == to and not system and not renote:
        raise ConflictError(f"The finding is already {to.value}.")
    if not system:
        allowed = OFFICER_EDGES.get(current, frozenset())
        if to not in allowed and not renote:
            raise UnprocessableError(
                f"A finding that is {current.value} cannot move to {to.value}. "
                f"Allowed: {sorted(s.value for s in allowed) or 'none'}.",
                code="invalid_finding_transition",
            )
        if to in REASON_REQUIRED and len(reason) < 5:
            raise UnprocessableError(
                f"A reason of at least 5 characters is required to mark a finding {to.value}.",
                code="reason_required",
            )

    finding.status = to
    if to in CLOSING:
        finding.resolution_reason = reason
        finding.resolved_at = utcnow()
    elif to == S.REOPENED:
        finding.resolved_at = None
    row = FindingTransition(
        finding_id=finding.id,
        application_id=finding.application_id,
        from_status=current.value,
        to_status=to.value,
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else "system",
        actor_role=_val(actor.role) if actor else "system",
        reason=reason or (reason_label or ""),
    )
    db.add(row)
    return row


def supersede_previous_runs(
    db: Session, application_id: str, current_run_id: str, *, note: str
) -> int:
    """After a fresh validation run, retire still-active findings from older runs.

    Their evidence (a document version or a rule result) has been re-processed, so they are
    ``superseded`` rather than silently counted or lost. Closed officer decisions are kept as-is.
    """
    stale = (
        db.query(Finding)
        .filter(
            Finding.application_id == application_id,
            Finding.validation_run_id != current_run_id,
            Finding.status.in_(list(ACTIVE_FINDING_STATUSES)),
        )
        .all()
    )
    for f in stale:
        apply_transition(db, f, S.SUPERSEDED, actor=None, system=True, reason=note)
    return len(stale)


def history(db: Session, finding_id: str) -> list[FindingTransition]:
    return (
        db.query(FindingTransition)
        .filter(FindingTransition.finding_id == finding_id)
        .order_by(FindingTransition.created_at.asc())
        .all()
    )
