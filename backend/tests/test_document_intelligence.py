"""Document-intelligence gaps: weak filename classification and image clarity.

These are deterministic checks on synthetic inputs. They are not a labelled-dataset accuracy score.
"""

import io

from PIL import Image

from app.document_processing.clarity import _assess_image
from app.document_processing.intelligence_types import PageText
from app.document_processing.semantic_classifier import SemanticDocumentClassifier
from app.models.enums import SemanticDocumentCategory


def _page(text: str) -> list[PageText]:
    return [PageText(page_number=1, text=text, source="pdf_text", char_count=len(text))]


def test_filename_alone_is_low_confidence():
    result = SemanticDocumentClassifier().classify(
        file_name="fire_noc.pdf",
        pages=_page("See attached scan."),
        selected_requirement_code="FIRE_NOC",
    )
    assert result.category == SemanticDocumentCategory.FIRE_NOC
    assert result.method == "keyword_heuristic_filename"
    assert result.confidence is not None and result.confidence < 0.5
    assert result.signals["filename_only"] is True


def test_document_text_outranks_a_misleading_filename():
    result = SemanticDocumentClassifier().classify(
        file_name="fire_noc.pdf",
        pages=_page("This affidavit is solemnly sworn by the deponent."),
        selected_requirement_code="AFFIDAVIT",
    )
    assert result.category == SemanticDocumentCategory.AFFIDAVIT
    assert result.signals["filename_only"] is False
    assert result.confidence is not None and result.confidence >= 0.5


def test_blank_image_is_unreadable_and_a_sharp_pattern_is_clear():
    blank = Image.new("RGB", (400, 400), (250, 250, 250))
    blank_result = _assess_image(blank)
    assert blank_result["level"] == "unreadable"
    assert "blank" in blank_result["message"].lower()

    sharp = Image.new("L", (400, 400), 255)
    px = sharp.load()
    for y in range(400):
        for x in range(400):
            px[x, y] = 0 if (x + y) % 2 == 0 else 255
    sharp_result = _assess_image(sharp)
    assert sharp_result["level"] == "clear"

    tiny = Image.new("RGB", (40, 40), (10, 10, 10))
    # give it some contrast so size, not blankness, is the reason
    buf = io.BytesIO()
    tiny.save(buf, format="PNG")
    tiny_result = _assess_image(Image.open(buf))
    assert tiny_result["level"] == "unclear"
    assert "small" in tiny_result["message"].lower()
