"""Issuer registry: store issued documents; verify uploads after OCR/extraction."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.core.security import ensure_application_access
from app.models.application import Application
from app.models.document import Document, DocumentVersion
from app.models.enums import UserRole
from app.models.issuer_registry import IssuerRegistryRecord, IssuerVerifyEvent
from app.models.user import User
from app.services.audit_service import record_audit

# Affidavit variants share the AFFIDAVIT registry bucket.
_DOC_TYPE_ALIASES: dict[str, str] = {
    "AFFIDAVIT_2": "AFFIDAVIT",
}

# Certificate numbers aligned with data/demo_pack OCR text + demo attach synthetics.
DEMO_RECORDS: list[dict[str, Any]] = [
    {
        "id": "reg-fire-pass-001",
        "doc_type": "FIRE_NOC",
        "certificate_number": "FIRE-VERIFIED-001",
        "issuer_name": "Municipal Fire Department",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Matches demo_pack 01_FIRE_NOC_pass.pdf — live verify PASS.",
    },
    {
        "id": "reg-fire-expired-pack",
        "doc_type": "FIRE_NOC",
        "certificate_number": "FIRE-EXPIRED-001",
        "issuer_name": "Municipal Fire Department",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Matches demo_pack expired NOC (still registered; date rules are separate).",
    },
    {
        "id": "reg-fire-seed-001",
        "doc_type": "FIRE_NOC",
        "certificate_number": "FIRE-2020-99",
        "issuer_name": "Demo Fire Service",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Seeded fire NOC number used in DB demo fixtures.",
    },
    {
        "id": "reg-affidavit-001",
        "doc_type": "AFFIDAVIT",
        "certificate_number": "AFF-DEMO-2024-1001",
        "issuer_name": "Notary Public — Pune",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Embedded in demo-attach synthetic affidavit PDFs.",
    },
    {
        "id": "reg-land-pack",
        "doc_type": "LAND_OWNERSHIP",
        "certificate_number": "45/2",
        "issuer_name": "Sub-Registrar — Pune",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Matches demo_pack land survey number.",
    },
    {
        "id": "reg-land-seed",
        "doc_type": "LAND_OWNERSHIP",
        "certificate_number": "12/4",
        "issuer_name": "Sub-Registrar — Pune",
        "holder_name": "Demo Tech College (Different Name)",
        "content_hash": "",
        "status": "issued",
        "notes": "Seed fixture survey number.",
    },
    {
        "id": "reg-affiliation-001",
        "doc_type": "AFFILIATION",
        "certificate_number": "SPPU-AFF-ENG-2025-88",
        "issuer_name": "Savitribai Phule Pune University",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Embedded in demo-attach affiliation letter.",
    },
    {
        "id": "reg-building-001",
        "doc_type": "BUILDING_PLAN",
        "certificate_number": "BP-PMC-2024-331",
        "issuer_name": "Pune Municipal Corporation — Building Permission",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Embedded in demo-attach building plan.",
    },
    {
        "id": "reg-occupancy-001",
        "doc_type": "OCCUPANCY_CERTIFICATE",
        "certificate_number": "BLD-VERIFIED-001",
        "issuer_name": "Municipal Corporation",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "issued",
        "notes": "Matches demo_pack occupancy certificate.",
    },
    {
        "id": "reg-revoked-001",
        "doc_type": "FIRE_NOC",
        "certificate_number": "FIRE-REVOKED-0001",
        "issuer_name": "Demo Fire Service",
        "holder_name": "Demo Institute of Technology",
        "content_hash": "",
        "status": "revoked",
        "notes": "Intentionally revoked — type this number to demo failure path.",
    },
]


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _names_match(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return True  # skip holder check if either side empty
    if na == nb:
        return True
    # Soft match for demo: one contains the other
    return na in nb or nb in na


def ensure_issuer_registry_seed(db: Session) -> None:
    """Idempotent demo issuer records for live authenticity checks."""
    changed = False
    for row in DEMO_RECORDS:
        existing = db.get(IssuerRegistryRecord, row["id"])
        if existing is None:
            db.add(
                IssuerRegistryRecord(
                    id=row["id"],
                    doc_type=row["doc_type"],
                    certificate_number=row["certificate_number"],
                    issuer_name=row["issuer_name"],
                    holder_name=row["holder_name"],
                    content_hash=row.get("content_hash") or "",
                    status=row.get("status") or "issued",
                    notes=row.get("notes") or "",
                    is_demo=True,
                )
            )
            changed = True
    if changed:
        db.commit()


def list_records(db: Session, user: User) -> list[dict[str, Any]]:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT):
        raise ForbiddenError("Not permitted.")
    rows = (
        db.query(IssuerRegistryRecord)
        .order_by(IssuerRegistryRecord.doc_type.asc(), IssuerRegistryRecord.certificate_number.asc())
        .all()
    )
    return [_record_out(r) for r in rows]


def _record_out(r: IssuerRegistryRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "docType": r.doc_type,
        "certificateNumber": r.certificate_number,
        "issuerName": r.issuer_name,
        "holderName": r.holder_name,
        "contentHash": r.content_hash or None,
        "status": r.status,
        "notes": r.notes,
        "isDemo": r.is_demo,
    }


def _field_map(doc: Document) -> dict[str, str]:
    version = doc.latest_version
    if version is None:
        return {}
    out: dict[str, str] = {}
    for f in version.extracted_fields or []:
        key = (f.field_name or "").strip().lower()
        val = (f.normalized_value or f.value or f.raw_value or "").strip()
        if key and val:
            out[key] = val
    return out


def build_verify_payload_from_document(
    db: Session, document_id: str, user: User | None = None
) -> dict[str, Any]:
    doc = (
        db.query(Document)
        .options(joinedload(Document.versions).joinedload(DocumentVersion.extracted_fields))
        .filter(Document.id == document_id)
        .first()
    )
    if doc is None:
        raise NotFoundError("Document not found.")
    if user is not None:
        app = db.get(Application, doc.application_id)
        if app is None:
            raise NotFoundError("Application not found.")
        ensure_application_access(user, app)
    fields = _field_map(doc)
    version = doc.latest_version
    cert = (
        fields.get("certificate_number")
        or fields.get("certificate_no")
        or fields.get("registration_number")
        or fields.get("survey_number")
        or ""
    )
    holder = fields.get("institution_name") or fields.get("holder_name") or ""
    raw_type = doc.requirement_code or ""
    doc_type = _DOC_TYPE_ALIASES.get(raw_type, raw_type)
    return {
        "docType": doc_type,
        "certificateNumber": cert,
        "holderName": holder,
        "issuerNameHint": fields.get("issuing_authority") or fields.get("issuer") or "",
        "contentHash": (version.sha256 if version else "") or "",
        "applicationId": doc.application_id,
        "documentId": doc.id,
        "extractedFields": fields,
        "requirementCode": raw_type,
    }


def verify(
    db: Session,
    user: User,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Hit-point for demo: compare OCR-derived fields against the issuer registry."""
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT):
        raise ForbiddenError("Not permitted to call issuer registry verify.")

    t0 = time.perf_counter()
    raw_type = (body.get("docType") or body.get("doc_type") or "").strip()
    doc_type = _DOC_TYPE_ALIASES.get(raw_type, raw_type)
    cert = (body.get("certificateNumber") or body.get("certificate_number") or "").strip()
    holder = (body.get("holderName") or body.get("holder_name") or "").strip()
    content_hash = (body.get("contentHash") or body.get("content_hash") or "").strip().lower()
    application_id = body.get("applicationId") or body.get("application_id")
    document_id = body.get("documentId") or body.get("document_id")

    if application_id:
        app = db.get(Application, application_id)
        if app is None:
            raise NotFoundError("Application not found.")
        ensure_application_access(user, app)

    if not cert:
        raise UnprocessableError(
            "certificateNumber is required (from OCR / extracted fields).",
            code="missing_certificate_number",
        )

    q = db.query(IssuerRegistryRecord).filter(
        IssuerRegistryRecord.certificate_number == cert
    )
    if doc_type:
        q = q.filter(IssuerRegistryRecord.doc_type == doc_type)
    record = q.first()
    # Fallback: match certificate across types if typed filter missed
    if record is None and doc_type:
        record = (
            db.query(IssuerRegistryRecord)
            .filter(IssuerRegistryRecord.certificate_number == cert)
            .first()
        )

    checks: dict[str, bool] = {
        "numberFound": record is not None,
        "holderMatch": False,
        "hashMatch": False,
        "notRevoked": False,
        "docTypeMatch": False,
    }
    result = "not_found"
    message = f"No issuer registry record for certificate '{cert}'."
    matched_id = None

    if record is not None:
        matched_id = record.id
        checks["docTypeMatch"] = not doc_type or record.doc_type == doc_type
        checks["holderMatch"] = _names_match(holder, record.holder_name)
        checks["notRevoked"] = record.status != "revoked"
        if record.content_hash and content_hash:
            checks["hashMatch"] = record.content_hash.lower() == content_hash
        else:
            # No registered hash → hash check not applicable; treat as pass for demo
            checks["hashMatch"] = True

        if not checks["notRevoked"]:
            result = "revoked"
            message = "Certificate was found but marked REVOKED by the issuer."
        elif not checks["holderMatch"]:
            result = "holder_mismatch"
            message = (
                f"Certificate found, but holder does not match. "
                f"Registry: '{record.holder_name}' · Document: '{holder or '(empty)'}'."
            )
        elif not checks["hashMatch"]:
            result = "hash_mismatch"
            message = "Certificate found, but file hash does not match the registered issued file."
        elif not checks["docTypeMatch"]:
            result = "type_mismatch"
            message = (
                f"Certificate found under doc type '{record.doc_type}', "
                f"but the upload is typed as '{doc_type}'."
            )
        else:
            result = "authentic"
            message = (
                f"Matches issuer registry ({record.issuer_name}). "
                "Document appears authentic against the registered record."
            )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    endpoint = "/api/v1/issuer-registry/verify"
    request_echo = {
        "method": "POST",
        "endpoint": endpoint,
        "body": {
            "docType": doc_type or None,
            "certificateNumber": cert,
            "holderName": holder or None,
            "contentHash": content_hash or None,
            "applicationId": application_id,
            "documentId": document_id,
        },
    }
    response_body = {
        "result": result,
        "authentic": result == "authentic",
        "message": message,
        "confidence": "high" if result == "authentic" else "medium" if record else "low",
        "checks": checks,
        "matchedRecord": _record_out(record) if record else None,
        "latencyMs": latency_ms,
        "disclaimer": (
            "Demo issuer registry: authentic means 'matches a registered issuer record', "
            "not a government legal determination."
        ),
        "endpoint": endpoint,
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
    }

    ev = IssuerVerifyEvent(
        application_id=application_id,
        document_id=document_id,
        actor_id=user.id,
        request_payload=json.dumps(request_echo, default=str),
        result=result,
        response_payload=json.dumps(response_body, default=str),
        latency_ms=latency_ms,
        matched_record_id=matched_id,
    )
    db.add(ev)
    record_audit(
        db,
        action="issuer_registry.verify",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"{result}: {cert}" + (f" ({doc_type})" if doc_type else ""),
        application_id=application_id,
        metadata={"result": result, "certificateNumber": cert, "latencyMs": latency_ms},
    )
    db.commit()

    return {
        **response_body,
        "request": request_echo,
        "verifyEventId": ev.id,
    }


def verify_document(db: Session, user: User, document_id: str) -> dict[str, Any]:
    """Convenience: build payload from OCR fields on the document, then verify."""
    payload = build_verify_payload_from_document(db, document_id, user)
    if not payload.get("certificateNumber"):
        # Demo fallback: invent nothing — return structured miss so UI can explain
        raise UnprocessableError(
            "OCR/extraction did not find a certificate number on this document. "
            "Enter one manually or re-run extraction.",
            code="missing_certificate_number",
            extra={"suggestedPayload": payload},
        )
    return verify(db, user, payload)


def recent_events(db: Session, user: User, *, limit: int = 20) -> list[dict[str, Any]]:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise ForbiddenError("Only officers can list verify events.")
    rows = (
        db.query(IssuerVerifyEvent)
        .order_by(IssuerVerifyEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "result": r.result,
                "latencyMs": r.latency_ms,
                "applicationId": r.application_id,
                "documentId": r.document_id,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "request": json.loads(r.request_payload) if r.request_payload else {},
                "response": json.loads(r.response_payload) if r.response_payload else {},
            }
        )
    return out
