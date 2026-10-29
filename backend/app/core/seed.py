from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.application import Application
from app.models.category import ApplicationCategory
from app.models.document import Document, DocumentVersion, ExtractedField
from app.models.enums import (
    ApplicationStatus,
    DocumentStatus,
    ExtractionMethod,
    ExternalVerificationLayerStatus,
    FieldReviewStatus,
    FindingSeverity,
    FindingStatus,
    Priority,
    RuleValidationStatus,
    UserRole,
    ValidationOutcome,
    ValidationRunStatus,
    DocumentReviewStatus,
)
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.user import Institution, User
from app.models.validation import Finding, FindingEvidence, ValidationRun


DEFAULT_DOCS = [
    {"code": "AFFIDAVIT", "name": "Sworn Affidavit", "mandatory": True, "allowed_types": ["pdf"]},
    {
        "code": "LAND_OWNERSHIP",
        "name": "Land Ownership / Lease Deed",
        "mandatory": True,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "AFFILIATION",
        "name": "University Affiliation Letter",
        "mandatory": True,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "BUILDING_PLAN",
        "name": "Building Plan Approval",
        "mandatory": True,
        "allowed_types": ["pdf", "jpg", "png"],
    },
    {
        "code": "FIRE_NOC",
        "name": "Fire Safety Certificate / NOC",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    # Phase 7 document types (config-driven three-layer verification)
    {
        "code": "AICTE_PAYMENT_RECEIPT",
        "name": "AICTE Payment Receipt",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "OCCUPANCY_CERTIFICATE",
        "name": "Occupancy / Completion Certificate / Building License / Form D",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "STRUCTURAL_STABILITY",
        "name": "Structural Stability Certificate",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "SATELLITE_MAP",
        "name": "Satellite Map",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "png"],
    },
    {
        "code": "AUDITED_ACCOUNTS",
        "name": "Previous-year Audited Statement of Accounts",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "AFFIDAVIT_2",
        "name": "Affidavit 2",
        "mandatory": False,
        "allowed_types": ["pdf", "jpg", "jpeg", "png"],
    },
    {
        "code": "SITE_LAB_PHOTOS",
        "name": "Laboratory photographs (equipment & labs)",
        "mandatory": True,
        "allowed_types": ["jpg", "jpeg", "png"],
    },
    {
        "code": "SITE_FACILITY_PHOTOS",
        "name": "Library / classroom / amenities photographs",
        "mandatory": True,
        "allowed_types": ["jpg", "jpeg", "png"],
    },
]


def seed_if_empty(db: Session) -> None:
    if db.query(Institution).count() > 0:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    inst = Institution(
        id="inst-001",
        name="Demo Institute of Technology",
        code="DEMO-INST-001",
        state="Maharashtra",
        type="Engineering",
    )
    db.add(inst)

    db.add_all(
        [
            User(
                id="usr-app-001",
                name="Dr. Ananya Mehta",
                email="registrar@demo-institute.edu",
                role=UserRole.APPLICANT,
                institution_id="inst-001",
                is_active=True,
            ),
            User(
                id="usr-off-001",
                name="Rajesh Iyer",
                email="officer.demo@aicte.example",
                role=UserRole.OFFICER,
                is_active=True,
            ),
            User(
                id="usr-off-002",
                name="Sneha Kulkarni",
                email="officer2.demo@aicte.example",
                role=UserRole.OFFICER,
                is_active=True,
            ),
            User(
                id="usr-adm-001",
                name="Priya Nair",
                email="regional.demo@praman.local",
                role=UserRole.REGIONAL_OFFICER,
                is_active=True,
            ),
        ]
    )

    categories = [
        ("NEW-ENG", "New Institution — Engineering"),
        ("EOA", "Extension of Approval"),
        ("INTAKE", "Increase in Intake"),
        ("NEW-MBA", "New Program — MBA"),
    ]
    cat_objs = []
    for code, name in categories:
        cat = ApplicationCategory(
            code=code,
            name=name,
            description=f"Demo category {code}",
            required_documents=DEFAULT_DOCS,
            is_active=True,
        )
        db.add(cat)
        cat_objs.append(cat)
    db.flush()

    for code, name, logic in [
        ("SYN-RULE-001", "[SYNTHETIC] Mandatory document checklist", "missing_mandatory"),
        ("SYN-RULE-003", "[SYNTHETIC] Affiliation validity window", "filename_contains_expired"),
        ("SYN-RULE-007", "[SYNTHETIC] Cross-document identity consistency", "cross_identity"),
    ]:
        rule = RegulatoryRule(
            code=code,
            name=name,
            description="Synthetic demo rule — not an official AICTE requirement.",
            handbook_ref="Demo handbook (placeholder — not official AICTE APH)",
            is_synthetic=True,
            is_active=True,
            current_version="v0.1-demo",
        )
        db.add(rule)
        db.flush()
        db.add(
            RuleVersion(
                rule_id=rule.id,
                version="v0.1-demo",
                definition={"logic": logic, "synthetic": True},
                status="published",
                change_reason="Seeded synthetic demo version",
                effective_from=now,
                published_at=now,
            )
        )


    new_eng = next(c for c in cat_objs if c.code == "NEW-ENG")
    app = Application(
        id="app-1001",
        application_number="PRM-2025-1001",
        institution_id="inst-001",
        category_id=new_eng.id,
        created_by_id="usr-app-001",
        assigned_officer_id="usr-off-001",
        program_name="B.Tech — Computer Science",
        academic_year="2025-26",
        contact_email="registrar@demo-institute.edu",
        status=ApplicationStatus.AWAITING_REVIEW,
        priority=Priority.HIGH,
        priority_score=72,
        finding_count=1,
        requires_manual_review=True,
        submitted_at=now,
    )
    db.add(app)
    db.flush()

    run = ValidationRun(
        application_id=app.id,
        status=ValidationRunStatus.COMPLETED,
        trigger="seed",
        triggered_by_id="usr-off-001",
        engine_version="0.1.0",
        rule_set_version="v0.1-demo",
        summary={"note": "seeded demo run"},
        started_at=now,
        completed_at=now,
    )
    db.add(run)
    db.flush()

    finding = Finding(
        application_id=app.id,
        validation_run_id=run.id,
        title="Institution name mismatch across documents",
        description=(
            "[SYNTHETIC] Extracted institution names differ. Requires officer confirmation. "
            "Not an official AICTE determination."
        ),
        severity=FindingSeverity.MANUAL_REVIEW,
        status=FindingStatus.OPEN,
        outcome=ValidationOutcome.MANUAL_REVIEW,
        rule_code="SYN-RULE-007",
        rule_name="[SYNTHETIC] Cross-document identity consistency",
        rule_version="v0.1-demo",
        handbook_ref="Demo handbook §A.B (placeholder)",
    )
    db.add(finding)
    db.flush()
    db.add(
        FindingEvidence(
            finding_id=finding.id,
            description="Seeded demo evidence for walkthrough",
            document_name="affidavit.pdf",
            page_reference="p.1",
            rule_code="SYN-RULE-007",
            rule_version="v0.1-demo",
        )
    )

    # ---- Repeatable SIH demo fixtures (files on disk + explainable statuses) ----
    upload_root = get_settings().upload_path
    upload_root.mkdir(parents=True, exist_ok=True)

    def _pdf_bytes(lines: list[str]) -> bytes:
        try:
            import fitz

            doc = fitz.open()
            page = doc.new_page()
            y = 72
            for line in lines:
                page.insert_text((72, y), line[:120], fontsize=11)
                y += 16
            data = doc.tobytes()
            doc.close()
            return data
        except Exception:  # noqa: BLE001 — fallback minimal PDF
            stream = "\\n".join(lines).encode("latin-1", errors="replace")
            return (
                b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + stream
            )

    def _store_doc(
        *,
        application_id: str,
        requirement_code: str,
        name: str,
        file_name: str,
        lines: list[str],
        fields: dict[str, str] | None = None,
        rule_status: RuleValidationStatus = RuleValidationStatus.PENDING,
        external_status: ExternalVerificationLayerStatus = ExternalVerificationLayerStatus.PENDING,
        review_status: DocumentReviewStatus = DocumentReviewStatus.PENDING,
    ) -> Document:
        content = _pdf_bytes(lines)
        sha = hashlib.sha256(content).hexdigest()
        storage_name = f"{application_id}_{requirement_code}_v1_{sha[:12]}_{file_name}"
        path = upload_root / storage_name
        path.write_bytes(content)
        doc = Document(
            application_id=application_id,
            requirement_code=requirement_code,
            name=name,
            current_version=1,
            status=DocumentStatus.UPLOADED,
            rule_validation_status=rule_status,
            external_verification_status=external_status,
            review_status=review_status,
        )
        db.add(doc)
        db.flush()
        ver = DocumentVersion(
            document_id=doc.id,
            version=1,
            file_name=file_name,
            extension="pdf",
            mime_type="application/pdf",
            size_bytes=len(content),
            sha256=sha,
            storage_path=str(path),
            page_count=1,
            file_checks={"ok": True, "source": "seed", "sha256": sha},
            validation_outcome=ValidationOutcome.PASS,
            uploaded_by_id="usr-app-001",
        )
        db.add(ver)
        db.flush()
        for fname, fval in (fields or {}).items():
            db.add(
                ExtractedField(
                    document_version_id=ver.id,
                    application_id=application_id,
                    field_name=fname,
                    value=fval,
                    raw_value=fval,
                    normalized_value=fval,
                    confidence=None,
                    page_number=1,
                    page_reference="p.1",
                    method=ExtractionMethod.MANUAL,
                    review_status=FieldReviewStatus.PENDING,
                )
            )
        return doc

    # app-1001: mismatched institution names + expired fire NOC + Phase7 payment (unavailable external)
    _store_doc(
        application_id=app.id,
        requirement_code="AFFIDAVIT",
        name="Sworn Affidavit",
        file_name="affidavit.pdf",
        lines=[
            "Institution Name: Demo Institute of Technology",
            "Document Type: Affidavit",
            "Issue Date: 2024-01-15",
        ],
        fields={"institution_name": "Demo Institute of Technology", "issue_date": "2024-01-15"},
        rule_status=RuleValidationStatus.PASS,
        external_status=ExternalVerificationLayerStatus.NOT_APPLICABLE,
        review_status=DocumentReviewStatus.NOT_REQUIRED,
    )
    _store_doc(
        application_id=app.id,
        requirement_code="LAND_OWNERSHIP",
        name="Land Ownership / Lease Deed",
        file_name="land_deed.pdf",
        lines=[
            "Institution Name: Demo Tech College (Different Name)",
            "Survey Number: 12/4",
            "Issue Date: 2023-06-01",
        ],
        fields={
            "institution_name": "Demo Tech College (Different Name)",
            "survey_number": "12/4",
            "issue_date": "2023-06-01",
        },
        rule_status=RuleValidationStatus.WARNING,
        review_status=DocumentReviewStatus.PENDING,
    )
    _store_doc(
        application_id=app.id,
        requirement_code="FIRE_NOC",
        name="Fire Safety Certificate / NOC",
        file_name="fire_noc_expired.pdf",
        lines=[
            "Certificate Number: FIRE-2020-99",
            "Issuing Authority: Demo Fire Service",
            "Issue Date: 2020-01-01",
            "Valid Until: 2021-01-01",
        ],
        fields={
            "certificate_number": "FIRE-2020-99",
            "issuing_authority": "Demo Fire Service",
            "issue_date": "2020-01-01",
            "valid_until": "2021-01-01",
        },
        rule_status=RuleValidationStatus.FAIL,
        external_status=ExternalVerificationLayerStatus.SOURCE_UNAVAILABLE,
        review_status=DocumentReviewStatus.PENDING,
    )
    _store_doc(
        application_id=app.id,
        requirement_code="AICTE_PAYMENT_RECEIPT",
        name="AICTE Payment Receipt",
        file_name="aicte_payment_receipt.pdf",
        lines=[
            "Receipt Number: RCPT-DEMO-001",
            "Payment Amount: 100000",
            "Payment Date: 2025-03-01",
            "Transaction ID: UTRDEMO123",
        ],
        fields={
            "receipt_number": "RCPT-DEMO-001",
            "payment_amount": "100000",
            "payment_date": "2025-03-01",
            "transaction_id": "UTRDEMO123",
        },
        rule_status=RuleValidationStatus.PASS,
        external_status=ExternalVerificationLayerStatus.SOURCE_UNAVAILABLE,
        review_status=DocumentReviewStatus.PENDING,
    )

    # app-1002: relatively clean complete mandatory set
    clean = Application(
        id="app-1002",
        application_number="PRM-2025-1002",
        institution_id="inst-001",
        category_id=new_eng.id,
        created_by_id="usr-app-001",
        program_name="B.Tech — Electronics",
        academic_year="2025-26",
        contact_email="registrar@demo-institute.edu",
        status=ApplicationStatus.UNDER_SCRUTINY,
        priority=Priority.LOW,
        priority_score=18,
        finding_count=0,
        requires_manual_review=False,
        submitted_at=now,
    )
    db.add(clean)
    db.flush()
    for code, name, fname in [
        ("AFFIDAVIT", "Sworn Affidavit", "clean_affidavit.pdf"),
        ("LAND_OWNERSHIP", "Land Ownership / Lease Deed", "clean_land.pdf"),
        ("AFFILIATION", "University Affiliation Letter", "clean_affiliation.pdf"),
        ("BUILDING_PLAN", "Building Plan Approval", "clean_building.pdf"),
    ]:
        _store_doc(
            application_id=clean.id,
            requirement_code=code,
            name=name,
            file_name=fname,
            lines=[
                "Institution Name: Demo Institute of Technology",
                f"Document: {name}",
                "Issue Date: 2025-01-10",
                "Valid Until: 2027-01-10",
            ],
            fields={
                "institution_name": "Demo Institute of Technology",
                "issue_date": "2025-01-10",
                "valid_until": "2027-01-10",
            },
            rule_status=RuleValidationStatus.PASS,
            external_status=ExternalVerificationLayerStatus.NOT_APPLICABLE,
            review_status=DocumentReviewStatus.NOT_REQUIRED,
        )

    # app-1003: missing mandatory documents (only affidavit)
    missing = Application(
        id="app-1003",
        application_number="PRM-2025-1003",
        institution_id="inst-001",
        category_id=new_eng.id,
        created_by_id="usr-app-001",
        program_name="B.Tech — Mechanical",
        academic_year="2025-26",
        contact_email="registrar@demo-institute.edu",
        status=ApplicationStatus.UNDER_SCRUTINY,
        priority=Priority.MEDIUM,
        priority_score=40,
        finding_count=1,
        requires_manual_review=True,
        submitted_at=now,
    )
    db.add(missing)
    db.flush()
    _store_doc(
        application_id=missing.id,
        requirement_code="AFFIDAVIT",
        name="Sworn Affidavit",
        file_name="only_affidavit.pdf",
        lines=["Institution Name: Demo Institute of Technology", "Issue Date: 2025-02-01"],
        fields={"institution_name": "Demo Institute of Technology", "issue_date": "2025-02-01"},
        rule_status=RuleValidationStatus.PASS,
        review_status=DocumentReviewStatus.NOT_REQUIRED,
    )
    miss_run = ValidationRun(
        application_id=missing.id,
        status=ValidationRunStatus.COMPLETED,
        trigger="seed",
        triggered_by_id="usr-off-001",
        engine_version="0.1.0",
        rule_set_version="v0.1-demo",
        summary={"note": "seeded missing-docs scenario"},
        started_at=now,
        completed_at=now,
    )
    db.add(miss_run)
    db.flush()
    db.add(
        Finding(
            application_id=missing.id,
            validation_run_id=miss_run.id,
            title="Missing mandatory documents",
            description=(
                "[SYNTHETIC] LAND_OWNERSHIP, AFFILIATION, and BUILDING_PLAN are missing. "
                "Not an official AICTE determination."
            ),
            severity=FindingSeverity.FAILED,
            status=FindingStatus.OPEN,
            outcome=ValidationOutcome.FAILED,
            rule_code="SYN-RULE-001",
            rule_name="[SYNTHETIC] Mandatory document checklist",
            rule_version="v0.1-demo",
            handbook_ref="Demo handbook (placeholder)",
        )
    )

    db.commit()


# Accounts the frontend role switcher logs in as. They must stay active in demo mode.
DEMO_SWITCHER_USER_IDS = ("usr-app-001", "usr-off-001", "usr-off-002", "usr-adm-001")


def ensure_regional_demo_users(db: Session) -> None:
    """Idempotent: second scrutiny officer + regional role rename for existing demo DBs."""
    changed = False
    if db.get(User, "usr-off-002") is None:
        db.add(
            User(
                id="usr-off-002",
                name="Sneha Kulkarni",
                email="officer2.demo@aicte.example",
                role=UserRole.OFFICER,
                is_active=True,
            )
        )
        changed = True
    # The role switcher cannot log in if a demo account was deactivated from Users & Roles.
    for uid in DEMO_SWITCHER_USER_IDS:
        u = db.get(User, uid)
        if u is not None and not u.is_active:
            u.is_active = True
            changed = True
    regional = db.get(User, "usr-adm-001")
    if regional is not None and regional.role != UserRole.REGIONAL_OFFICER:
        regional.role = UserRole.REGIONAL_OFFICER
        if regional.email == "admin.demo@praman.local":
            regional.email = "regional.demo@praman.local"
        changed = True
    # Seeded walkthrough applications must be visible to the demo scrutiny officer
    # (officers only see applications delegated to them).
    for seeded_id in ("app-1002", "app-1003"):
        seeded = db.get(Application, seeded_id)
        if seeded is not None and not seeded.assigned_officer_id:
            seeded.assigned_officer_id = "usr-off-001"
            changed = True
    if changed:
        db.commit()


SITE_PHOTO_DOCS = [
    {
        "code": "SITE_LAB_PHOTOS",
        "name": "Laboratory photographs (equipment & labs)",
        "mandatory": True,
        "allowed_types": ["jpg", "jpeg", "png"],
    },
    {
        "code": "SITE_FACILITY_PHOTOS",
        "name": "Library / classroom / amenities photographs",
        "mandatory": True,
        "allowed_types": ["jpg", "jpeg", "png"],
    },
]


def ensure_site_photo_requirements(db: Session) -> None:
    """Idempotent: add lab + library photo slots to every category checklist and published snapshot."""
    from app.models.category_config import CategoryConfigVersion, DocumentRequirement
    from app.services.category_config_service import _req_runtime, sync_requirements_from_json

    changed = False
    for cat in db.query(ApplicationCategory).all():
        docs = list(cat.required_documents or [])
        existing = {str(d.get("code") or "") for d in docs if isinstance(d, dict)}
        added = False
        for photo in SITE_PHOTO_DOCS:
            if photo["code"] not in existing:
                docs.append(dict(photo))
                added = True
        if added:
            cat.required_documents = docs
            changed = True
        sync_requirements_from_json(db, cat, docs if docs else list(DEFAULT_DOCS))

        # Patch published / draft config snapshots so pinned applications see the new slots.
        versions = (
            db.query(CategoryConfigVersion)
            .filter(CategoryConfigVersion.category_id == cat.id)
            .all()
        )
        by_code = {
            r.code: r
            for r in db.query(DocumentRequirement)
            .filter(DocumentRequirement.category_id == cat.id, DocumentRequirement.is_active.is_(True))
            .all()
        }
        for ver in versions:
            snap = dict(ver.snapshot or {})
            reqs = list(snap.get("requirements") or [])
            have = {str(r.get("code") or "") for r in reqs if isinstance(r, dict)}
            snap_changed = False
            for photo in SITE_PHOTO_DOCS:
                code = photo["code"]
                if code in have:
                    continue
                row = by_code.get(code)
                if row is None:
                    continue
                item = _req_runtime(row)
                item["rules"] = []
                reqs.append(item)
                snap_changed = True
            if snap_changed:
                snap["requirements"] = reqs
                ver.snapshot = snap
                changed = True

    if changed:
        db.commit()


def ensure_upload_paths_repaired(db: Session) -> None:
    """Copy misplaced upload files into UPLOAD_DIR and rewrite storage_path to relative names."""
    from pathlib import Path

    from app.core.config import get_settings
    from app.integrations.storage import resolve_upload_file
    from app.models.document import DocumentVersion

    root = get_settings().upload_path
    root.mkdir(parents=True, exist_ok=True)
    changed = False
    for ver in db.query(DocumentVersion).all():
        resolved = resolve_upload_file(ver.storage_path, root)
        if resolved is None:
            continue
        rel = resolved.name
        # Prefer keeping existing relative path when already under root with full relative name
        try:
            rel_path = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_path = rel
        if ver.storage_path != rel_path:
            ver.storage_path = rel_path
            changed = True
    if changed:
        db.commit()


_IMAGE_OK = ["pdf", "jpg", "jpeg", "png"]
_CODES_ALLOW_IMAGES = {
    "AFFIDAVIT",
    "AFFIDAVIT_2",
    "LAND_OWNERSHIP",
    "AFFILIATION",
    "BUILDING_PLAN",
    "FIRE_NOC",
    "OCCUPANCY_CERTIFICATE",
    "STRUCTURAL_STABILITY",
    "AICTE_PAYMENT_RECEIPT",
    "AUDITED_ACCOUNTS",
    "SATELLITE_MAP",
    "SITE_LAB_PHOTOS",
    "SITE_FACILITY_PHOTOS",
    "SITE_CAMPUS_PHOTOS",
}


def ensure_demo_image_types(db: Session) -> None:
    """Allow jpg/png on demo checklist slots that use scanned test images."""
    from app.models.category_config import CategoryConfigVersion, DocumentRequirement
    from app.services.category_config_service import sync_requirements_from_json

    changed = False
    for cat in db.query(ApplicationCategory).all():
        docs = list(cat.required_documents or [])
        docs_changed = False
        for d in docs:
            if not isinstance(d, dict):
                continue
            code = str(d.get("code") or "")
            if code not in _CODES_ALLOW_IMAGES:
                continue
            types = [str(x).lower().lstrip(".") for x in (d.get("allowed_types") or [])]
            merged = list(dict.fromkeys([*types, *_IMAGE_OK]))
            if merged != types:
                d["allowed_types"] = merged
                docs_changed = True
        if docs_changed:
            cat.required_documents = docs
            changed = True
            sync_requirements_from_json(db, cat, docs)
        # Patch requirement rows + snapshots even if JSON was already updated earlier.
        for row in (
            db.query(DocumentRequirement)
            .filter(DocumentRequirement.category_id == cat.id, DocumentRequirement.is_active.is_(True))
            .all()
        ):
            if row.code not in _CODES_ALLOW_IMAGES:
                continue
            types = [str(x).lower().lstrip(".") for x in (row.allowed_types or [])]
            merged = list(dict.fromkeys([*types, *_IMAGE_OK]))
            if merged != types:
                row.allowed_types = merged
                changed = True
        for ver in db.query(CategoryConfigVersion).filter(CategoryConfigVersion.category_id == cat.id).all():
            snap = dict(ver.snapshot or {})
            reqs = list(snap.get("requirements") or [])
            snap_changed = False
            for r in reqs:
                if not isinstance(r, dict):
                    continue
                if str(r.get("code") or "") not in _CODES_ALLOW_IMAGES:
                    continue
                types = [str(x).lower().lstrip(".") for x in (r.get("allowed_types") or [])]
                merged = list(dict.fromkeys([*types, *_IMAGE_OK]))
                if merged != types:
                    r["allowed_types"] = merged
                    snap_changed = True
            if snap_changed:
                snap["requirements"] = reqs
                ver.snapshot = snap
                changed = True
    if changed:
        db.commit()

