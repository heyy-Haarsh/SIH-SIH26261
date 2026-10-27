"""JSON + PDF scrutiny reports (decision-support only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.application import Application
from app.models.doc_verification import DocumentVerificationRun
from app.schemas.engine import ApplicationResultOut, TriageScoreOut
from app.services.serializers import to_application_result_out, to_document_result_out

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "scrutiny_report.html"

DECISION_NOTICE = (
    "Decision-support output; final decision rests with the competent authority."
)


def generate_application_report(db: Session, application_id: str) -> ApplicationResultOut:
    app = db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application not found")
    runs = (
        db.query(DocumentVerificationRun)
        .filter(DocumentVerificationRun.application_id == application_id)
        .order_by(DocumentVerificationRun.created_at.desc())
        .all()
    )
    # keep latest run per document
    latest: dict[str, DocumentVerificationRun] = {}
    for r in runs:
        if r.document_id not in latest:
            latest[r.document_id] = r
    result = to_application_result_out(
        application_id=application_id,
        runs=list(latest.values()),
        rule_set_version="scrutiny-weights-v1",
        engine_version="praman-engine-0.1",
        overall_status="manual_review_required",
    )
    if DECISION_NOTICE not in result.report_disclaimer:
        result.report_disclaimer = f"{result.report_disclaimer} {DECISION_NOTICE}"
    return result


def render_report_html(report: ApplicationResultOut) -> str:
    tpl = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return tpl.render(
        report=report,
        decision_notice=DECISION_NOTICE,
        generated_at=report.generated_at.isoformat(),
    )


def generate_application_report_pdf(db: Session, application_id: str) -> bytes:
    """Formatted PDF built from the same grouped review the officer sees (reportlab)."""
    from app.services.pdf_report_service import generate_scrutiny_pdf

    return generate_scrutiny_pdf(db, application_id)
