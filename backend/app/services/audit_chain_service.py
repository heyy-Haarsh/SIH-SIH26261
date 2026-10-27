"""Hash-chained audit log service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_chain import AuditChainEvent
from app.models.base import utcnow


def _row_payload(ev: AuditChainEvent) -> str:
    return "|".join(
        [
            str(ev.sequence),
            ev.action,
            ev.actor_id or "",
            ev.actor_role or "",
            ev.application_id or "",
            ev.entity_type or "",
            ev.entity_id or "",
            ev.rule_version or "",
            ev.connector_used or "",
            ev.mode or "",
            ev.input_hash or "",
            ev.result_summary or "",
            ev.prev_hash or "",
            ev.created_at.isoformat() if ev.created_at else "",
        ]
    )


def _hash_payload(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{payload}".encode("utf-8")).hexdigest()


def record_chain_event(
    db: Session,
    *,
    action: str,
    actor_id: str = "",
    actor_role: str = "",
    application_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    rule_version: Optional[str] = None,
    connector_used: Optional[str] = None,
    mode: str = "REAL",
    input_hash: Optional[str] = None,
    result_summary: str | dict[str, Any] = "",
) -> AuditChainEvent:
    last = db.scalar(select(AuditChainEvent).order_by(AuditChainEvent.sequence.desc()).limit(1))
    prev = last.chain_hash if last else ("0" * 64)
    next_seq = (last.sequence + 1) if last else 1
    summary = result_summary if isinstance(result_summary, str) else json.dumps(result_summary, sort_keys=True)
    ev = AuditChainEvent(
        sequence=next_seq,
        action=action,
        actor_id=actor_id or "",
        actor_role=actor_role or "",
        application_id=application_id,
        entity_type=entity_type,
        entity_id=entity_id,
        rule_version=rule_version,
        connector_used=connector_used,
        mode=mode,
        input_hash=input_hash,
        result_summary=summary,
        created_at=utcnow(),
        prev_hash=prev,
        chain_hash="",  # filled below
    )
    # Temporary hash input uses empty chain_hash placeholder in payload — exclude chain_hash from payload
    payload = _row_payload(ev)
    ev.chain_hash = _hash_payload(prev, payload)
    db.add(ev)
    db.flush()
    return ev


@dataclass
class IntegrityResult:
    ok: bool
    checked: int
    first_bad_sequence: Optional[int] = None
    detail: str = ""


def verify_chain_integrity(
    db: Session, from_seq: int | None = None, to_seq: int | None = None
) -> IntegrityResult:
    q = select(AuditChainEvent).order_by(AuditChainEvent.sequence.asc())
    rows = list(db.scalars(q).all())
    if from_seq is not None:
        rows = [r for r in rows if r.sequence >= from_seq]
    if to_seq is not None:
        rows = [r for r in rows if r.sequence <= to_seq]
    if not rows:
        return IntegrityResult(ok=True, checked=0, detail="empty chain")
    expected_prev = ("0" * 64) if rows[0].sequence == 1 else rows[0].prev_hash
    # If starting mid-chain, trust first prev_hash
    if rows[0].sequence != 1:
        expected_prev = rows[0].prev_hash
    else:
        expected_prev = "0" * 64
    checked = 0
    for i, row in enumerate(rows):
        if i == 0 and row.sequence == 1 and row.prev_hash != ("0" * 64):
            return IntegrityResult(ok=False, checked=checked, first_bad_sequence=row.sequence, detail="bad genesis prev_hash")
        if i > 0 and row.prev_hash != rows[i - 1].chain_hash:
            return IntegrityResult(
                ok=False, checked=checked, first_bad_sequence=row.sequence, detail="prev_hash mismatch"
            )
        payload = _row_payload(row)
        expected = _hash_payload(row.prev_hash, payload)
        if expected != row.chain_hash:
            return IntegrityResult(
                ok=False, checked=checked, first_bad_sequence=row.sequence, detail="chain_hash mismatch"
            )
        checked += 1
        expected_prev = row.chain_hash
    return IntegrityResult(ok=True, checked=checked, detail="intact")
