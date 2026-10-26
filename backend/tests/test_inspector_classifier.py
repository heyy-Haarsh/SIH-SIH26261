from app.document_processing.inspector import DocumentInspector
from app.document_processing.intelligence_types import PageText
from app.document_processing.semantic_classifier import (
    SemanticDocumentClassifier,
    is_category_mismatch,
)
from app.models.enums import DocumentContentKind, SemanticDocumentCategory


def test_inspect_empty():
    r = DocumentInspector().inspect(content=b"", extension="pdf")
    assert r.content_kind == DocumentContentKind.UNREADABLE
    assert r.error_code == "empty_file"


def test_inspect_text():
    r = DocumentInspector().inspect(content=b"Institution Name: X\n", extension="txt")
    assert r.content_kind == DocumentContentKind.TEXT
    assert r.readable


def test_inspect_pdf_magic_without_crash():
    # Minimal PDF header — may be corrupt for PyMuPDF; must not crash process
    content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    r = DocumentInspector().inspect(content=content, extension="pdf")
    assert r.content_kind in {
        DocumentContentKind.DIGITAL_PDF,
        DocumentContentKind.SCANNED_PDF,
        DocumentContentKind.MIXED_PDF,
        DocumentContentKind.UNREADABLE,
    }


def test_semantic_affidavit():
    pages = [PageText(page_number=1, text="This affidavit is solemnly sworn by the deponent.", source="pdf_text", char_count=50)]
    c = SemanticDocumentClassifier().classify(file_name="sworn_affidavit.pdf", pages=pages, selected_requirement_code="AFFIDAVIT")
    assert c.category == SemanticDocumentCategory.AFFIDAVIT


def test_semantic_unknown():
    pages = [PageText(page_number=1, text="hello world", source="pdf_text", char_count=11)]
    c = SemanticDocumentClassifier().classify(file_name="doc.pdf", pages=pages)
    assert c.category == SemanticDocumentCategory.UNKNOWN


def test_category_mismatch():
    assert is_category_mismatch(SemanticDocumentCategory.FIRE_NOC, "AFFIDAVIT") is True
    assert is_category_mismatch(SemanticDocumentCategory.UNKNOWN, "AFFIDAVIT") is False
