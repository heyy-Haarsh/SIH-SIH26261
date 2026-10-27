"""Formatted PDF scrutiny report (reportlab). Decision support only — never an automatic verdict."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.application import Application
from app.schemas.scrutiny import (
    DocumentReportOut,
    HandbookReferenceOut,
    ScrutinyIssueOut,
    ScrutinyReviewOut,
)
from app.services import document_report_service, scrutiny_view_service

INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#d1d5db")
HEAD_BG = colors.HexColor("#f3f4f6")
SEVERITY_COLOR = {
    "failed": colors.HexColor("#b91c1c"),
    "manual_review": colors.HexColor("#b45309"),
    "warning": colors.HexColor("#a16207"),
    "info": colors.HexColor("#4b5563"),
}
SEVERITY_LABEL = {
    "failed": "Failed",
    "manual_review": "Needs review",
    "warning": "Warning",
    "info": "Note",
}
STAGE_LABEL = {
    "pass": "Passed",
    "warning": "Warning",
    "failed": "Failed",
    "manual_review": "Needs review",
    "unavailable": "Unavailable",
    "not_run": "Not run",
}
STATUS_LABEL = {
    "open": "Open",
    "resolved": "Resolved",
    "waived": "Waived",
    "accepted": "Accepted",
}

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_UNICODE_FONT = False


def _setup_fonts() -> None:
    """Use a Unicode font when one is installed so Marathi/Hindi names survive; else Helvetica."""
    global _FONT, _FONT_BOLD, _UNICODE_FONT
    if _UNICODE_FONT:
        return
    candidates = [
        ("C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/NirmalaB.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists():
            try:
                pdfmetrics.registerFont(TTFont("PramanSans", regular))
                bold_path = bold if bold and Path(bold).exists() else regular
                pdfmetrics.registerFont(TTFont("PramanSans-Bold", bold_path))
                _FONT, _FONT_BOLD, _UNICODE_FONT = "PramanSans", "PramanSans-Bold", True
                return
            except Exception:  # noqa: BLE001 — fall back to the built-in font
                continue


def _t(text: str | None) -> str:
    """Escape for Paragraph markup and, with the built-in font, drop unsupported glyphs."""
    s = (text or "").replace("\r", "")
    if not _UNICODE_FONT:
        s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s).replace("\n", "<br/>")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName=_FONT_BOLD, fontSize=20, textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontName=_FONT, fontSize=9.5, textColor=MUTED, spaceAfter=8),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], fontName=_FONT_BOLD, fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading3"], fontName=_FONT_BOLD, fontSize=10.5, textColor=INK, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("b", parent=base["Normal"], fontName=_FONT, fontSize=9, leading=12.5, textColor=INK),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontName=_FONT, fontSize=8, leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontName=_FONT, fontSize=8.5, leading=11, textColor=INK),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontName=_FONT_BOLD, fontSize=8.5, leading=11, textColor=INK),
        "notice": ParagraphStyle("n", parent=base["Normal"], fontName=_FONT, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#92400e")),
    }


class _NumberedCanvas(rl_canvas.Canvas):
    """Adds 'Page x of y' and a running footer after the page count is known."""

    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        w, _ = A4
        self.setStrokeColor(BORDER)
        self.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
        self.setFont(_FONT, 7.5)
        self.setFillColor(MUTED)
        self.drawString(18 * mm, 10.5 * mm, self.footer_text)
        self.drawRightString(w - 18 * mm, 10.5 * mm, f"Page {self._pageNumber} of {total}")


def _handbook_text(h: HandbookReferenceOut) -> str:
    if h.status == "verified":
        parts = [h.edition or "", f"§{h.section}" if h.section else "", f"p. {h.page}" if h.page else ""]
        return " · ".join(p for p in parts if p)
    return "Not verified"


def _issue_rows(issues: list[ScrutinyIssueOut], st: dict) -> list[list]:
    rows = [
        [
            Paragraph("Severity", st["cellb"]),
            Paragraph("Issue", st["cellb"]),
            Paragraph("What the applicant should correct", st["cellb"]),
            Paragraph("Handbook reference", st["cellb"]),
        ]
    ]
    for i in issues:
        sev = SEVERITY_LABEL.get(i.severity, i.severity)
        status = STATUS_LABEL.get(i.status, i.status)
        color = SEVERITY_COLOR.get(i.severity, INK).hexval()[2:]
        extra = f" ×{i.occurrences}" if i.occurrences > 1 else ""
        rows.append(
            [
                Paragraph(f'<font color="#{color}"><b>{_t(sev)}</b></font><br/>{_t(status)}', st["cell"]),
                Paragraph(f"<b>{_t(i.title)}</b>{_t(extra)}<br/>{_t(i.explanation)}", st["cell"]),
                Paragraph(_t(i.applicant_action or "—"), st["cell"]),
                Paragraph(_t(_handbook_text(i.handbook)), st["cell"]),
            ]
        )
    return rows


def _table(rows: list[list], widths: list[float], *, header: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    t.setStyle(TableStyle(style))
    return t


def render_pdf(review: ScrutinyReviewOut, reports: list[DocumentReportOut], program: str, year: str) -> bytes:
    _setup_fonts()
    st = _styles()
    buf = BytesIO()
    _NumberedCanvas.footer_text = f"PRAMAN scrutiny report · {review.application_number} · decision support only"
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"Scrutiny report {review.application_number}",
        author="PRAMAN",
    )
    width = A4[0] - 36 * mm
    story: list = []

    story.append(Paragraph("Scrutiny Report", st["title"]))
    story.append(
        Paragraph(
            _t(f"{review.application_number} · {review.institution_name}"),
            st["sub"],
        )
    )

    meta = [
        ["Institution", review.institution_name or "—"],
        ["Programme", f"{program} ({year})" if program else "—"],
        ["Application status", review.status.replace("_", " ")],
        ["Generated", review.generated_at.strftime("%d %b %Y, %H:%M UTC")],
        [
            "Latest validation",
            review.validation_completed_at.strftime("%d %b %Y, %H:%M UTC")
            if review.validation_completed_at
            else "Not run",
        ],
    ]
    story.append(
        _table(
            [[Paragraph(_t(k), st["cellb"]), Paragraph(_t(v), st["cell"])] for k, v in meta],
            [38 * mm, width - 38 * mm],
            header=False,
        )
    )
    story.append(Spacer(1, 6))
    notice = Table(
        [[Paragraph(_t(review.disclaimer), st["notice"])]],
        colWidths=[width],
    )
    notice.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#f59e0b")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(notice)

    # ---- summary -----------------------------------------------------------------
    story.append(Paragraph("Summary", st["h1"]))
    summary = [
        ["Documents uploaded", str(len(review.documents))],
        ["Required documents missing", str(len([m for m in review.missing_documents if m.mandatory]))],
        ["Open issues", str(review.open_issue_count)],
        ["Resolved / waived / accepted", str(review.resolved_issue_count)],
        ["Earlier-run findings kept as history", str(review.historical_finding_count)],
    ]
    story.append(
        _table(
            [[Paragraph(_t(k), st["cellb"]), Paragraph(_t(v), st["cell"])] for k, v in summary],
            [70 * mm, width - 70 * mm],
            header=False,
        )
    )

    # ---- decision ----------------------------------------------------------------
    d = review.decision
    story.append(Paragraph("Decision and clarification", st["h1"]))
    if d.final_decision:
        story.append(
            Paragraph(
                _t(
                    f"Recorded decision: {d.final_decision.upper()}"
                    + (f" by {d.final_decision_by}" if d.final_decision_by else "")
                ),
                st["body"],
            )
        )
        story.append(Paragraph(_t(f"Reason: {d.final_decision_reason or '—'}"), st["body"]))
    else:
        story.append(Paragraph("No final decision has been recorded.", st["body"]))
    if d.clarification_requests:
        story.append(Paragraph("Clarification requests", st["h2"]))
        rows = [
            [
                Paragraph("Request", st["cellb"]),
                Paragraph("Status", st["cellb"]),
                Paragraph("Applicant response", st["cellb"]),
            ]
        ]
        for c in d.clarification_requests:
            rows.append(
                [
                    Paragraph(f"<b>{_t(c.title)}</b><br/>{_t(c.description)}", st["cell"]),
                    Paragraph(_t(c.status), st["cell"]),
                    Paragraph(_t(c.applicant_response or "—"), st["cell"]),
                ]
            )
        story.append(_table(rows, [width * 0.5, width * 0.15, width * 0.35]))
    if d.must_correct:
        story.append(Paragraph("What the applicant must correct", st["h2"]))
        for n, m in enumerate(d.must_correct, 1):
            story.append(Paragraph(_t(f"{n}. {m}"), st["body"]))

    # ---- issues ------------------------------------------------------------------
    story.append(Paragraph("Issues by document", st["h1"]))
    if review.missing_documents:
        story.append(
            Paragraph(
                _t(
                    "Not uploaded: "
                    + ", ".join(
                        f"{m.name}{'' if m.mandatory else ' (optional)'}" for m in review.missing_documents
                    )
                ),
                st["body"],
            )
        )
    if not review.issue_groups:
        story.append(Paragraph("No issues were recorded by the latest validation run.", st["body"]))
    for g in review.issue_groups:
        head = Paragraph(
            _t(f"{g.document_name}  —  {g.open_count} open"),
            st["h2"],
        )
        rows = _issue_rows(g.issues, st)
        tbl = _table(rows, [width * 0.13, width * 0.42, width * 0.28, width * 0.17])
        story.append(KeepTogether([head, tbl]) if len(rows) < 6 else head)
        if len(rows) >= 6:
            story.append(tbl)
        story.append(Spacer(1, 4))

    # ---- pipeline ----------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Verification pipeline per document", st["h1"]))
    story.append(
        Paragraph(
            "Stages are independent: a pass at one stage says nothing about the next. "
            "Layer 1 rules passing is not proof of authenticity.",
            st["small"],
        )
    )
    for rep in reports:
        c = rep.document
        story.append(
            Paragraph(
                _t(f"{c.name} — {c.file_name} (v{c.version})"),
                st["h2"],
            )
        )
        rows = [[Paragraph("Stage", st["cellb"]), Paragraph("Result", st["cellb"]), Paragraph("Summary", st["cellb"])]]
        for s in rep.stages:
            rows.append(
                [
                    Paragraph(_t(s.title), st["cell"]),
                    Paragraph(f"<b>{_t(STAGE_LABEL.get(s.status, s.status))}</b>", st["cell"]),
                    Paragraph(_t(s.summary), st["cell"]),
                ]
            )
        story.append(_table(rows, [width * 0.30, width * 0.14, width * 0.56]))
        story.append(Spacer(1, 4))

    # ---- limitations -------------------------------------------------------------
    if review.limitations:
        story.append(Paragraph("Known limitations of this report", st["h1"]))
        for lim in review.limitations:
            story.append(Paragraph(_t(f"• {lim}"), st["body"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            _t(
                "Handbook references are shown only when an administrator has verified edition, "
                "section and page. “Not verified” means no verified citation is on record."
            ),
            st["small"],
        )
    )

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()


def generate_scrutiny_pdf(db: Session, application_id: str) -> bytes:
    app = db.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found")
    review = scrutiny_view_service.build_review(db, app)
    reports = [
        document_report_service.build_document_report(db, app, d.id)
        for d in app.documents
        if d.latest_version
    ]
    return render_pdf(review, reports, app.program_name, app.academic_year)
