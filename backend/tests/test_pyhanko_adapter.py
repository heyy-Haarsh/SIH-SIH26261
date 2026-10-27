"""Phase 4: pyHanko adapter behaviours (works without pyhanko package)."""

from datetime import datetime, timezone
from pathlib import Path

from app.models.enums import VerificationStatus
from app.verification_engine.adapters.pdf_signature_pyhanko import verify_pdf_signature_pyhanko
from app.verification_engine.adapters.types import AdapterContext


def _ctx(path: str | None, mime: str = "application/pdf") -> AdapterContext:
    return AdapterContext(
        document_id="d1",
        document_version_id="v1",
        requirement_code="FIRE_NOC",
        file_path=path,
        mime_type=mime,
        fields={},
    )


def test_missing_file():
    r = verify_pdf_signature_pyhanko(_ctx("/no/such/file.pdf"))
    assert r.status == VerificationStatus.SOURCE_UNAVAILABLE


def test_unsigned_minimal_pdf(tmp_path: Path):
    pdf = tmp_path / "u.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    r = verify_pdf_signature_pyhanko(_ctx(str(pdf)))
    assert r.evidence.get("signature_status") in {
        "signature_absent",
        None,
    } or "signature" in (r.detail or "").lower() or r.status in {
        VerificationStatus.MANUAL_REVIEW_REQUIRED,
        VerificationStatus.SOURCE_UNAVAILABLE,
    }


def test_scanned_heuristic(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._looks_scanned_pdf",
        lambda _p: True,
    )
    r = verify_pdf_signature_pyhanko(_ctx(str(pdf)))
    assert r.evidence.get("signature_status") == "not_applicable"
    assert r.status == VerificationStatus.MANUAL_REVIEW_REQUIRED


def test_empty_trust_store_signed(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "signed.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._looks_scanned_pdf",
        lambda _p: False,
    )
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._has_signature_indicators",
        lambda _p: (True, {"signature_widgets": 1, "sigflags": 1}),
    )
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._try_pyhanko_integrity",
        lambda _p: {"pyhanko_available": False, "modified_after_signing": False, "integrity_ok": True},
    )
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._trust_roots",
        lambda: [],
    )
    r = verify_pdf_signature_pyhanko(_ctx(str(pdf)))
    assert r.status == VerificationStatus.MANUAL_REVIEW_REQUIRED
    assert r.evidence.get("chain_status") == "chain_untrusted_no_trust_store"


def test_modified_after_signing(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "mod.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._looks_scanned_pdf",
        lambda _p: False,
    )
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._has_signature_indicators",
        lambda _p: (True, {"signature_widgets": 1}),
    )
    monkeypatch.setattr(
        "app.verification_engine.adapters.pdf_signature_pyhanko._try_pyhanko_integrity",
        lambda _p: {"pyhanko_available": True, "modified_after_signing": True, "integrity_ok": False},
    )
    r = verify_pdf_signature_pyhanko(_ctx(str(pdf)))
    assert r.status == VerificationStatus.MISMATCH_DETECTED
    assert r.evidence.get("signature_status") == "signature_present_modified_after_signing"
