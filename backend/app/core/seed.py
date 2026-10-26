from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.category import ApplicationCategory
from app.models.enums import ApplicationStatus, FindingSeverity, FindingStatus, Priority, UserRole, ValidationOutcome
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.user import Institution, User
from app.models.validation import Finding, FindingEvidence, ValidationRun
from app.models.enums import ValidationRunStatus


DEFAULT_DOCS = [
    {"code": "AFFIDAVIT", "name": "Sworn Affidavit", "mandatory": True, "allowed_types": ["pdf"]},
    {
        "code": "LAND_OWNERSHIP",
        "name": "Land Ownership / Lease Deed",
        "mandatory": True,
        "allowed_types": ["pdf"],
    },
    {
        "code": "AFFILIATION",
        "name": "University Affiliation Letter",
        "mandatory": True,
        "allowed_types": ["pdf"],
    },
    {
        "code": "BUILDING_PLAN",
        "name": "Building Plan Approval",
        "mandatory": True,
        "allowed_types": ["pdf", "jpg", "png"],
    },
    {
        "code": "FIRE_NOC",
        "name": "Fire Safety NOC",
        "mandatory": False,
        "allowed_types": ["pdf"],
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
            ),
            User(
                id="usr-off-001",
                name="Rajesh Iyer",
                email="officer.demo@aicte.example",
                role=UserRole.OFFICER,
            ),
            User(
                id="usr-adm-001",
                name="Priya Nair",
                email="admin.demo@praman.local",
                role=UserRole.ADMIN,
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
                effective_from=now,
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
    db.commit()
