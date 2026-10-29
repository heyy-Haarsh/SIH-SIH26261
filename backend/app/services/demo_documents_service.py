"""Attach synthetic demo files for every missing checklist slot (demo / walkthrough only)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ensure_application_access
from app.models.application import Application
from app.models.document import Document, DocumentVersion
from app.models.enums import (
    ApplicationStatus,
    DocumentStatus,
    UserRole,
    ValidationOutcome,
)
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.category_config_service import effective_requirements

# Prefer scanned images from data/test-images for demo attach (realistic walkthrough).
_TEST_IMAGE_MAP: dict[str, str] = {
    "AFFIDAVIT": "affidivat-2.png",
    "AFFIDAVIT_2": "affidivat-2.png",
    "LAND_OWNERSHIP": "registered-lease-deed.png",
    "AFFILIATION": "board-affiliation-letter.png",
    "BUILDING_PLAN": "approved-building-plan.png",
    "FIRE_NOC": "fire safety - noc.png",
    "OCCUPANCY_CERTIFICATE": "occupancy certificate.png",
    "AICTE_PAYMENT_RECEIPT": "payment receipt.png",
    "AUDITED_ACCOUNTS": "balance sheet.png",
    "SATELLITE_MAP": "satellite.png",
    "SITE_CAMPUS_PHOTOS": "satellite.png",
    "SITE_LAB_PHOTOS": "computer lab.png",
    "SITE_FACILITY_PHOTOS": "central library.png",
    "STRUCTURAL_STABILITY": "approved-building-plan.png",
}

# Fallback PDFs from demo_pack when a test image is missing.
_DEMO_PACK_MAP: dict[str, str] = {
    "FIRE_NOC": "01_FIRE_NOC_pass.pdf",
    "AICTE_PAYMENT_RECEIPT": "04_PAYMENT_pass.pdf",
    "OCCUPANCY_CERTIFICATE": "06_OCCUPANCY_pass.pdf",
    "STRUCTURAL_STABILITY": "07_STRUCTURAL_pass.pdf",
    "AUDITED_ACCOUNTS": "08_AUDITED_balance_ok.pdf",
    "SATELLITE_MAP": "10_SATELLITE_coords.pdf",
    "AFFIDAVIT_2": "11_AFFIDAVIT_2_pass.pdf",
    "AFFIDAVIT": "12_AFFIDAVIT_name_A.pdf",
    "LAND_OWNERSHIP": "13_LAND_name_B_fuzzy.pdf",
}

_IMAGE_CODES = {"SITE_CAMPUS_PHOTOS", "SITE_LAB_PHOTOS", "SITE_FACILITY_PHOTOS"}
_DEMO_IMAGE_MAX_EDGE = 1600

# Certificate / survey numbers registered in issuer_registry DEMO_RECORDS —
# embedded in synthetic PDFs so OCR → live verify works in the demo video.
_REGISTRY_LINES: dict[str, list[str]] = {
    "FIRE_NOC": [
        "Certificate Number: FIRE-VERIFIED-001",
        "Issuing Authority: Municipal Fire Department",
        "Valid Until: 2028-03-15",
    ],
    "AFFIDAVIT": [
        "Certificate Number: AFF-DEMO-2024-1001",
        "Issuing Authority: Notary Public — Pune",
        "Registration Number: AFF-DEMO-2024-1001",
    ],
    "AFFIDAVIT_2": [
        "Certificate Number: AFF-DEMO-2024-1001",
        "Issuing Authority: Notary Public — Pune",
    ],
    "LAND_OWNERSHIP": [
        "Survey Number: 45/2",
        "Certificate Number: 45/2",
        "Issuing Authority: Sub-Registrar — Pune",
    ],
    "AFFILIATION": [
        "Certificate Number: SPPU-AFF-ENG-2025-88",
        "Issuing Authority: Savitribai Phule Pune University",
        "Registration Number: SPPU-AFF-ENG-2025-88",
    ],
    "BUILDING_PLAN": [
        "Certificate Number: BP-PMC-2024-331",
        "Issuing Authority: Pune Municipal Corporation — Building Permission",
    ],
    "OCCUPANCY_CERTIFICATE": [
        "Certificate Number: BLD-VERIFIED-001",
        "Issuing Authority: Municipal Corporation",
    ],
}


def _repo_root() -> Path:
    # backend/app/services -> repo root
    return Path(__file__).resolve().parents[3]


def _repo_demo_pack() -> Path:
    return _repo_root() / "data" / "demo_pack"


def _repo_test_images() -> Path:
    return _repo_root() / "data" / "test-images"


def _load_test_image(filename: str) -> tuple[bytes, str, str, str] | None:
    """Load + lightly downscale a test-images scan for demo attach (keeps OCR workable)."""
    path = _repo_test_images() / filename
    if not path.is_file():
        return None
    raw = path.read_bytes()
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = "image/png" if ext == "png" else "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(raw))
        img = img.convert("RGB")
        w, h = img.size
        edge = max(w, h)
        if edge > _DEMO_IMAGE_MAX_EDGE:
            scale = _DEMO_IMAGE_MAX_EDGE / float(edge)
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        buf = BytesIO()
        # JPEG is much smaller than the source PNGs (~9MB) — faster demo attach / OCR.
        out_name = path.stem.replace(" ", "_") + ".jpg"
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue(), out_name, "jpg", "image/jpeg"
    except Exception:  # noqa: BLE001
        safe_name = filename.replace(" ", "_")
        return raw, safe_name, ext, mime


def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        y = 72
        page.insert_text((72, y), title[:100], fontsize=14)
        y += 28
        for line in lines:
            page.insert_text((72, y), line[:110], fontsize=11)
            y += 16
        data = doc.tobytes()
        doc.close()
        return data
    except Exception:  # noqa: BLE001
        body = "\n".join([title, *lines]).encode("latin-1", errors="replace")
        return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + body


def _png_bytes(label: str, *, width: int = 640, height: int = 400) -> bytes:
    """RGB PNG placeholder for campus / lab photo slots (Pillow)."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    upper = (label or "").upper()
    if "LAB" in upper:
        color = (90, 130, 90)
        caption = "Demo laboratory photo"
    elif "FACILITY" in upper or "LIBRARY" in upper:
        color = (140, 100, 80)
        caption = "Demo facility photo"
    else:
        color = (70, 110, 150)
        caption = "Demo campus photo"

    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([24, 24, width - 24, height - 24], outline=(255, 255, 255), width=3)
    draw.text((40, height // 2 - 10), caption[:60], fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _content_for_requirement(code: str, name: str, institution_name: str) -> tuple[bytes, str, str, str]:
    """Returns content, file_name, extension, mime_type."""
    # 1) Real scans from data/test-images (preferred for demo video).
    test_name = _TEST_IMAGE_MAP.get(code)
    if test_name:
        loaded = _load_test_image(test_name)
        if loaded is not None:
            return loaded

    # 2) demo_pack PDFs when present.
    pack = _repo_demo_pack()
    mapped = _DEMO_PACK_MAP.get(code)
    if mapped and (pack / mapped).is_file():
        data = (pack / mapped).read_bytes()
        if mapped.lower().endswith(".pdf"):
            return data, mapped, "pdf", "application/pdf"

    # 3) Synthetic site photo placeholders.
    if code in _IMAGE_CODES or any(t in (code or "").upper() for t in ("PHOTO", "IMAGE")):
        if code.startswith("SITE_") or code in _IMAGE_CODES:
            data = _png_bytes(name or code)
            fname = f"demo_{code.lower()}.png"
            return data, fname, "png", "image/png"

    # 4) Synthetic PDF with registry certificate lines (issuer-verify demo).
    lines = [
        f"Institution Name: {institution_name}",
        f"Requirement: {code}",
        f"Document: {name}",
        *(_REGISTRY_LINES.get(code) or []),
        "This is a synthetic demo file for SIH walkthroughs.",
        "Not an official AICTE submission.",
    ]
    data = _pdf_bytes(name or code, lines)
    fname = f"demo_{code.lower()}.pdf"
    return data, fname, "pdf", "application/pdf"


def attach_demo_documents(
    db: Session,
    user: User,
    application_id: str,
    *,
    include_optional: bool = True,
) -> dict:
    if user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=403, detail="Only applicants can attach demo documents.")

    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    if app.status in (
        ApplicationStatus.RECOMMENDED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.APPROVED,
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "application_closed",
                "message": "This application is closed; documents can no longer be changed.",
            },
        )

    reqs = effective_requirements(app)
    uploaded = {d.requirement_code for d in app.documents}
    targets = [
        r
        for r in reqs
        if r["code"] not in uploaded and (include_optional or r.get("mandatory", True))
    ]

    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    institution = app.institution_name or (app.institution.name if app.institution else "Demo Institute")
    attached: list[dict] = []

    for req in targets:
        code = req["code"]
        name = req.get("name") or code
        content, file_name, ext, mime = _content_for_requirement(code, name, institution)
        sha = hashlib.sha256(content).hexdigest()
        storage_name = f"{application_id}_{code}_v1_{sha[:12]}_{file_name}"
        path = settings.upload_path / storage_name
        path.write_bytes(content)

        doc = Document(
            application_id=application_id,
            requirement_code=code,
            requirement_id=req.get("id"),
            name=name,
            current_version=1,
            status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        db.flush()
        ver = DocumentVersion(
            document_id=doc.id,
            version=1,
            file_name=file_name,
            extension=ext,
            mime_type=mime,
            size_bytes=len(content),
            sha256=sha,
            storage_path=storage_name,
            page_count=1 if ext == "pdf" else None,
            file_checks={"ok": True, "source": "demo_attach", "sha256": sha},
            validation_outcome=ValidationOutcome.PASS,
            uploaded_by_id=user.id,
        )
        db.add(ver)
        db.flush()
        attached.append({"code": code, "name": name, "fileName": file_name})

    if attached:
        record_audit(
            db,
            action="document.demo_attached",
            actor=user.name,
            actor_id=user.id,
            actor_role=user.role.value,
            detail=f"Attached {len(attached)} demo document(s)",
            application_id=app.id,
        )
        db.commit()
    else:
        db.rollback()

    # Run type/readability (extraction) on every version that has no run yet —
    # including files that were attached earlier without checks.
    checked = _run_pending_document_checks(db, app, user)

    already = len(uploaded)
    msg_parts = []
    if attached:
        msg_parts.append(f"Attached {len(attached)} demo document(s)")
    elif not attached:
        msg_parts.append("All checklist slots already have documents")
    if checked:
        msg_parts.append(f"ran type/readability checks on {checked}")
    return {
        "attachedCount": len(attached),
        "attached": attached,
        "alreadyPresent": already,
        "checksRun": checked,
        "message": "; ".join(msg_parts) + ".",
    }


def _run_pending_document_checks(
    db: Session,
    app: Application,
    user: User,
    *,
    run_validation_pass: bool = False,
) -> int:
    """Best-effort extraction so applicant Type / Readability columns populate.

    Does **not** advance workflow status by default (validation would move the app
    into under_scrutiny). Pass ``run_validation_pass=True`` from Submit for scrutiny.
    """
    from app.core import runtime_config
    from app.document_processing.orchestrator import run_extraction_for_version
    from app.models.extraction import ExtractionRun

    app = db.query(Application).filter(Application.id == app.id).first()
    if app is None:
        return 0
    ran = 0
    for doc in list(app.documents):
        version = doc.latest_version
        if version is None:
            continue
        existing = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.document_version_id == version.id)
            .first()
        )
        if existing is not None:
            continue
        if not runtime_config.auto_extract_on_upload():
            continue
        try:
            run_extraction_for_version(
                db,
                version,
                application_id=app.id,
                selected_requirement_code=doc.requirement_code,
                triggered_by_id=user.id,
                force=False,
            )
            db.commit()
            ran += 1
        except Exception:  # noqa: BLE001 — demo helper must not fail the attach
            db.rollback()

    if run_validation_pass:
        try:
            from app.services.validation_service import run_validation

            app = db.query(Application).filter(Application.id == app.id).first()
            if app is not None:
                run_validation(db, app, triggered_by=user.id, actor_name=user.name)
        except Exception:  # noqa: BLE001
            db.rollback()
    return ran
