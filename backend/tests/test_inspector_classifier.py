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


def test_semantic_aicte_payment_receipt():
    pages = [
        PageText(
            page_number=1,
            text="AICTE payment receipt challan transaction fee for application.",
            source="pdf_text",
            char_count=60,
        )
    ]
    c = SemanticDocumentClassifier().classify(
        file_name="aicte_payment_receipt.pdf", pages=pages, selected_requirement_code="AICTE_PAYMENT_RECEIPT"
    )
    assert c.category == SemanticDocumentCategory.AICTE_PAYMENT_RECEIPT


def test_semantic_audited_accounts():
    pages = [
        PageText(
            page_number=1,
            text="Audited accounts and financial statements by chartered accountant.",
            source="pdf_text",
            char_count=66,
        )
    ]
    c = SemanticDocumentClassifier().classify(
        file_name="audited_accounts.pdf", pages=pages, selected_requirement_code="AUDITED_ACCOUNTS"
    )
    assert c.category == SemanticDocumentCategory.AUDITED_ACCOUNTS


def test_semantic_structural_stability():
    pages = [
        PageText(
            page_number=1,
            text="Structural stability certificate confirming seismic compliance.",
            source="pdf_text",
            char_count=62,
        )
    ]
    c = SemanticDocumentClassifier().classify(
        file_name="structural_stability.pdf",
        pages=pages,
        selected_requirement_code="STRUCTURAL_STABILITY",
    )
    assert c.category == SemanticDocumentCategory.STRUCTURAL_STABILITY


def test_semantic_satellite_map():
    pages = [
        PageText(
            page_number=1,
            text="Campus satellite geotag geotagged geolocation imagery.",
            source="pdf_text",
            char_count=54,
        )
    ]
    c = SemanticDocumentClassifier().classify(
        file_name="satellite_map.pdf", pages=pages, selected_requirement_code="SATELLITE_MAP"
    )
    assert c.category == SemanticDocumentCategory.SATELLITE_MAP


def test_semantic_affidavit_2():
    pages = [
        PageText(
            page_number=1,
            text="Estamp stamppaper notary stamp certificate reference.",
            source="pdf_text",
            char_count=52,
        )
    ]
    c = SemanticDocumentClassifier().classify(
        file_name="affidavit_2_estamp.pdf", pages=pages, selected_requirement_code="AFFIDAVIT_2"
    )
    assert c.category == SemanticDocumentCategory.AFFIDAVIT_2
