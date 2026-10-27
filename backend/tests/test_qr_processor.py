"""Phase 3: QR payload compare (no pyzbar required for parse/compare tests)."""

from app.document_processing.qr_processor import QRProcessor, compare_qr_to_fields


def test_qr_match():
    result = compare_qr_to_fields(
        ['{"certificate_number":"FIRE-001","institution_name":"Demo"}'],
        {"certificate_number": "FIRE-001", "institution_name": "Demo"},
    )
    assert result.status == "match"
    assert "certificate_number" in result.matched_fields


def test_qr_mismatch():
    result = compare_qr_to_fields(
        ["certificate_number=FIRE-001"],
        {"certificate_number": "FIRE-OTHER"},
    )
    assert result.status == "mismatch"
    assert "certificate_number" in result.mismatched_fields


def test_qr_absent():
    result = compare_qr_to_fields([], {"certificate_number": "x"})
    assert result.status == "qr_absent"


def test_qr_unreadable():
    result = compare_qr_to_fields(["%%%not-a-payload%%%"], {"certificate_number": "x"})
    assert result.status == "payload_unreadable"


def test_qr_processor_degrades_without_images():
    r = QRProcessor().check(image_bytes_list=[], extracted_fields={"a": "1"})
    assert r.status == "qr_absent"
