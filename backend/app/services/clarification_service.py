"""Rules for what counts as an answer to a clarification request.

A clarification may need an explanation, a replacement document, or both. The server decides
which is satisfied from persisted facts: the text supplied and the document versions that were
uploaded *after* the request was issued. A new upload never resolves a clarification by itself;
it only becomes part of the applicant's response when they submit one.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentVersion
from app.models.finding_transition import DeficiencyFinding
from app.models.review import DeficiencyNotice
from app.models.validation import Finding

MIN_TEXT = 5


@dataclass
class Replacement:
    document_id: str
    name: str
    version: int


def affected_document_ids(db: Session, notice: DeficiencyNotice) -> list[str]:
    """Documents the request is about (via its linked findings). Empty = application-wide."""
    rows = (
        db.query(Finding.document_id)
        .join(DeficiencyFinding, DeficiencyFinding.finding_id == Finding.id)
        .filter(DeficiencyFinding.deficiency_id == notice.id, Finding.document_id.isnot(None))
        .distinct()
        .all()
    )
    ids = [r[0] for r in rows]
    if notice.finding_id and not ids:
        legacy = db.query(Finding.document_id).filter(Finding.id == notice.finding_id).scalar()
        if legacy:
            ids = [legacy]
    return ids


def replacements_since_request(db: Session, notice: DeficiencyNotice) -> list[Replacement]:
    """Replacement versions (v2+) uploaded after the request, for the documents it concerns."""
    ids = affected_document_ids(db, notice)
    query = (
        db.query(DocumentVersion, Document)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(
            Document.application_id == notice.application_id,
            DocumentVersion.version > 1,
            DocumentVersion.uploaded_at > notice.created_at,
        )
    )
    if ids:
        query = query.filter(Document.id.in_(ids))
    best: dict[str, Replacement] = {}
    for version, doc in query.order_by(DocumentVersion.version).all():
        best[doc.id] = Replacement(document_id=doc.id, name=doc.name, version=version.version)
    return list(best.values())


def response_mode(text: str, replacements: list[Replacement]) -> str | None:
    has_text = len((text or "").strip()) >= MIN_TEXT
    if has_text and replacements:
        return "both"
    if has_text:
        return "text"
    if replacements:
        return "document"
    return None


def missing_for_response(db: Session, notice: DeficiencyNotice, text: str) -> str | None:
    """Plain-language reason a response cannot be accepted yet, or None when it can."""
    replacements = replacements_since_request(db, notice)
    if notice.requires_replacement and not replacements:
        return "The officer asked for a replacement document. Upload it first, then send your response."
    if response_mode(text, replacements) is None:
        return f"Write at least {MIN_TEXT} characters explaining your response, or upload the replacement."
    return None
