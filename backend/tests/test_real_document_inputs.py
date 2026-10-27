"""Real-file checks for text extraction and OCR.

Native PDF text uses PyMuPDF on a PDF this test builds. OCR cases call the Tesseract
binary on this machine when it is installed. They are skipped with an explicit reason
when it is not — a skip is not a pass. The fake-pytesseract cases live in
``test_applicant_p0.py`` and are mocks.
"""

import io
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.document_processing.ocr_processor import resolve_tesseract_cmd, tesseract_status
from app.document_processing.orchestrator import ExtractionOrchestrator
from app.models.enums import ExtractionRunStatus

_FONT = next(
    (
        p
        for p in (
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        if Path(p).is_file()
    ),
    None,
)
_MARATHI_FONT = next(
    (
        p
        for p in (
            r"C:\Windows\Fonts\Nirmala.ttf",
            r"C:\Windows\Fonts\nirmala.ttf",
            r"C:\Windows\Fonts\Nirmala.ttc",
            r"C:\Windows\Fonts\mangal.ttf",
        )
        if Path(p).is_file()
    ),
    None,
)


def _native_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Institution Name: Shivaji Institute of Technology")
    page.insert_text((72, 96), "This affidavit is solemnly sworn by the deponent.")
    data = doc.tobytes()
    doc.close()
    return data


def _image(text: str, font_path: str, size: int = 64) -> bytes:
    img = Image.new("RGB", (1600, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 140), text, fill="black", font=ImageFont.truetype(font_path, size))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _scanned_pdf(png: bytes) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=220)
    page.insert_image(page.rect, stream=png)
    data = doc.tobytes()
    doc.close()
    return data


def test_native_pdf_text_is_extracted_without_ocr():
    outcome = ExtractionOrchestrator().process_bytes(
        content=_native_pdf(),
        extension="pdf",
        file_name="affidavit.pdf",
        selected_requirement_code="AFFIDAVIT",
    )
    assert outcome.status in (
        ExtractionRunStatus.COMPLETED,
        ExtractionRunStatus.COMPLETED_WITH_WARNINGS,
    )
    assert outcome.pages_ocr == 0
    assert outcome.pages
    assert outcome.pages[0].source == "pdf_text"
    assert "Shivaji Institute of Technology" in outcome.pages[0].text
    names = [f.field_name for f in outcome.fields]
    assert "institution_name" in names
    inst = next(f for f in outcome.fields if f.field_name == "institution_name")
    assert inst.page_number == 1
    assert inst.raw_snippet


def test_tesseract_on_this_machine_is_discovered():
    cmd = resolve_tesseract_cmd()
    if cmd is None:
        pytest.skip("Tesseract executable is not installed; OCR cannot be executed here.")
    status = tesseract_status()
    assert status["available"] is True, status["message"]
    assert status["tesseract_cmd"] == cmd
    assert "eng" in status["languages_usable"]


def test_scanned_pdf_and_png_are_read_by_tesseract():
    if _FONT is None:
        pytest.skip("No Latin font available to render a scan fixture.")
    status = tesseract_status()
    if not status["available"] or "eng" not in status["languages_usable"]:
        pytest.skip(f"English OCR cannot run: {status['message']}")

    png = _image("AFFIDAVIT solemnly sworn", _FONT)
    image_out = ExtractionOrchestrator().process_bytes(
        content=png, extension="png", file_name="scan.png", selected_requirement_code="AFFIDAVIT"
    )
    assert image_out.pages_ocr == 1
    assert image_out.pages[0].source == "ocr"
    assert "affidavit" in image_out.pages[0].text.lower()

    scan = ExtractionOrchestrator().process_bytes(
        content=_scanned_pdf(png),
        extension="pdf",
        file_name="scan.pdf",
        selected_requirement_code="AFFIDAVIT",
    )
    assert scan.pages_ocr == 1
    assert "affidavit" in scan.pages[0].text.lower()
    assert scan.pages[0].source == "ocr"


def test_marathi_scan_invokes_the_marathi_language_pack():
    """The mar pack runs on a real rendered scan. Exact-word accuracy is not claimed.

    Measured on this machine (Tesseract 5.5, Nirmala, word प्रतिज्ञापत्र): the engine
    returned प्रतजिञापत्र. That is a misread, so this test only checks that Devanagari
    text came back from OCR rather than an empty or Latin substitute.
    """
    status = tesseract_status()
    if not status.get("marathi_supported"):
        pytest.skip(f"Marathi tessdata is not installed: {status['message']}")
    if _MARATHI_FONT is None:
        pytest.skip("No Devanagari font is installed, so a real Marathi scan cannot be rendered.")

    png = _image("प्रतिज्ञापत्र", _MARATHI_FONT, size=96)
    outcome = ExtractionOrchestrator().process_bytes(
        content=png, extension="png", file_name="affidavit.png", selected_requirement_code="AFFIDAVIT"
    )
    assert outcome.pages_ocr == 1
    assert outcome.pages[0].source == "ocr"
    text = outcome.pages[0].text
    assert any("\u0900" <= ch <= "\u097f" for ch in text), text


def test_empty_corrupt_and_unsupported_files_fail_explicitly():
    engine = ExtractionOrchestrator()
    empty = engine.process_bytes(content=b"", extension="pdf", file_name="empty.pdf")
    assert empty.status == ExtractionRunStatus.FAILED
    assert empty.error_code == "empty_file"

    corrupt = engine.process_bytes(content=b"%PDF-1.4 not a real body", extension="pdf", file_name="bad.pdf")
    assert corrupt.status in (ExtractionRunStatus.FAILED, ExtractionRunStatus.UNSUPPORTED)
    assert corrupt.error_code

    junk = engine.process_bytes(content=b"\x00\x01\x02not-a-document", extension="bin", file_name="notes.bin")
    assert junk.status == ExtractionRunStatus.UNSUPPORTED
    assert junk.pages_ocr == 0
