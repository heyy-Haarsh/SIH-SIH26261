"""Handbook reference lookup and administration.

Rules:
* A reference is ``verified`` only when edition, section and page are all present AND an
  administrator marked it verified.
* Everything else is returned as ``unverified`` with an explicit note. No clause is ever guessed,
  and legacy "(placeholder)" strings on old findings are never promoted to a citation.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, UnprocessableError
from app.models.base import utcnow
from app.models.handbook import HandbookReference
from app.models.user import User
from app.schemas.scrutiny import (
    HandbookReferenceAdminOut,
    HandbookReferenceIn,
    HandbookReferenceOut,
)
from app.services.audit_service import record_audit

UNVERIFIED_NOTE = (
    "No verified AICTE Approval Process Handbook reference is recorded for this rule. "
    "An administrator must add the edition, section and page after checking the handbook."
)


def _is_complete(ref: HandbookReference) -> bool:
    return bool(ref.edition.strip() and ref.section.strip() and ref.page.strip())


def to_out(ref: HandbookReference | None) -> HandbookReferenceOut:
    if ref is None:
        return HandbookReferenceOut(status="unverified", note=UNVERIFIED_NOTE)
    if ref.verified and _is_complete(ref):
        return HandbookReferenceOut(
            status="verified",
            edition=ref.edition,
            section=ref.section,
            page=ref.page,
            title=ref.title or None,
            note=ref.source_note or "",
        )
    missing = [
        label
        for label, value in (("edition", ref.edition), ("section", ref.section), ("page", ref.page))
        if not value.strip()
    ]
    reason = (
        f"Reference is incomplete (missing {', '.join(missing)})."
        if missing
        else "Reference has not been verified against the handbook by an administrator."
    )
    return HandbookReferenceOut(
        status="unverified",
        edition=ref.edition or None,
        section=ref.section or None,
        page=ref.page or None,
        title=ref.title or None,
        note=reason,
    )


class HandbookResolver:
    """Loads all references once per request."""

    def __init__(self, db: Session):
        self._by_key = {r.reference_key: r for r in db.query(HandbookReference).all()}

    def lookup(self, *keys: str | None) -> HandbookReferenceOut:
        for key in keys:
            if key and key in self._by_key:
                return to_out(self._by_key[key])
        return to_out(None)


# ---- admin -------------------------------------------------------------------


def _admin_out(ref: HandbookReference, db: Session) -> HandbookReferenceAdminOut:
    verified_by = None
    if ref.verified_by_id:
        u = db.query(User).filter(User.id == ref.verified_by_id).first()
        verified_by = u.name if u else ref.verified_by_id
    return HandbookReferenceAdminOut(
        id=ref.id,
        reference_key=ref.reference_key,
        edition=ref.edition,
        section=ref.section,
        page=ref.page,
        title=ref.title,
        source_note=ref.source_note,
        verified=bool(ref.verified and _is_complete(ref)),
        verified_by=verified_by,
        verified_at=ref.verified_at,
        updated_at=ref.updated_at,
    )


def list_references(db: Session) -> list[HandbookReferenceAdminOut]:
    rows = db.query(HandbookReference).order_by(HandbookReference.reference_key).all()
    return [_admin_out(r, db) for r in rows]


def upsert_reference(db: Session, user: User, payload: HandbookReferenceIn) -> HandbookReferenceAdminOut:
    edition, section, page = payload.edition.strip(), payload.section.strip(), payload.page.strip()
    if payload.verified and not (edition and section and page):
        raise UnprocessableError(
            "A reference can only be marked verified when edition, section and page are all given.",
            code="incomplete_reference",
        )
    ref = (
        db.query(HandbookReference)
        .filter(HandbookReference.reference_key == payload.reference_key)
        .first()
    )
    created = ref is None
    if ref is None:
        ref = HandbookReference(reference_key=payload.reference_key)
        db.add(ref)
    ref.edition, ref.section, ref.page = edition, section, page
    ref.title = payload.title.strip()
    ref.source_note = payload.source_note.strip()
    ref.verified = bool(payload.verified)
    ref.verified_by_id = user.id if payload.verified else None
    ref.verified_at = utcnow() if payload.verified else None
    record_audit(
        db,
        action="handbook.reference_created" if created else "handbook.reference_updated",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=(
            f"{payload.reference_key}: edition='{edition}' section='{section}' page='{page}' "
            f"verified={ref.verified}"
        ),
        entity_type="handbook_reference",
        entity_id=ref.id,
    )
    db.commit()
    db.refresh(ref)
    return _admin_out(ref, db)


def delete_reference(db: Session, user: User, reference_id: str) -> None:
    ref = db.query(HandbookReference).filter(HandbookReference.id == reference_id).first()
    if ref is None:
        raise NotFoundError("Handbook reference not found.")
    key = ref.reference_key
    db.delete(ref)
    record_audit(
        db,
        action="handbook.reference_deleted",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Removed reference for {key}",
        entity_type="handbook_reference",
        entity_id=reference_id,
    )
    db.commit()
