"""DocumentInspector — content-kind classification from actual bytes (not extension alone)."""

from __future__ import annotations

import io
import zipfile
from typing import Optional

from app.document_processing.intake import sniff_kind
from app.document_processing.intelligence_types import InspectResult
from app.models.enums import DocumentContentKind

# Lazy import PyMuPDF
def _fitz():
    try:
        import fitz  # PyMuPDF

        return fitz
    except ImportError:
        return None


MIN_TEXT_CHARS_PER_PAGE = 40


class DocumentInspector:
    name = "document_inspector"

    def inspect(self, *, content: bytes, extension: str, mime_type: str = "") -> InspectResult:
        if not content:
            return InspectResult(
                content_kind=DocumentContentKind.UNREADABLE,
                page_count=0,
                encrypted=False,
                readable=False,
                error_code="empty_file",
                error_message="File is empty.",
            )

        detected = sniff_kind(content)
        ext = extension.lower().lstrip(".")

        if detected == "unknown" and ext not in {"txt", "docx", "pdf", "png", "jpg", "jpeg"}:
            return InspectResult(
                content_kind=DocumentContentKind.UNSUPPORTED,
                page_count=None,
                readable=False,
                error_code="unsupported_content",
                error_message=f"Content signature '{detected}' is not a supported document type.",
                warnings=["Extension/content signature could not be reconciled."],
            )

        if detected in {"png", "jpeg"} or ext in {"png", "jpg", "jpeg"}:
            return self._inspect_image(content, detected)

        if detected == "text" or ext == "txt":
            return InspectResult(
                content_kind=DocumentContentKind.TEXT,
                page_count=1,
                readable=True,
                signals={"detected": detected},
            )

        if detected == "docx" or ext == "docx":
            return self._inspect_docx(content)

        if detected == "pdf" or ext == "pdf":
            return self._inspect_pdf(content)

        return InspectResult(
            content_kind=DocumentContentKind.UNSUPPORTED,
            page_count=None,
            readable=False,
            error_code="unsupported_content",
            error_message=f"Unsupported document kind (detected={detected}, ext={ext}).",
        )

    def _inspect_image(self, content: bytes, detected: str) -> InspectResult:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(content))
            img.verify()
            return InspectResult(
                content_kind=DocumentContentKind.IMAGE,
                page_count=1,
                readable=True,
                signals={"detected": detected, "format": getattr(img, "format", None)},
            )
        except Exception as exc:  # noqa: BLE001 — surface as unreadable
            return InspectResult(
                content_kind=DocumentContentKind.UNREADABLE,
                page_count=None,
                readable=False,
                error_code="image_decode_failed",
                error_message="Image could not be decoded.",
                warnings=[exc.__class__.__name__],
            )

    def _inspect_docx(self, content: bytes) -> InspectResult:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = set(zf.namelist())
            if "word/document.xml" not in names:
                return InspectResult(
                    content_kind=DocumentContentKind.UNREADABLE,
                    page_count=None,
                    readable=False,
                    error_code="corrupt_docx",
                    error_message="DOCX container is missing word/document.xml.",
                )
            return InspectResult(
                content_kind=DocumentContentKind.DOCX,
                page_count=None,
                readable=True,
                warnings=["DOCX text extraction is limited in this build; prefer PDF where possible."],
            )
        except zipfile.BadZipFile:
            return InspectResult(
                content_kind=DocumentContentKind.UNREADABLE,
                page_count=None,
                readable=False,
                error_code="corrupt_docx",
                error_message="DOCX/ZIP archive is corrupt.",
            )

    def _inspect_pdf(self, content: bytes) -> InspectResult:
        fitz = _fitz()
        if fitz is None:
            # Fall back to magic-byte only; cannot distinguish scanned vs digital without PyMuPDF
            return InspectResult(
                content_kind=DocumentContentKind.DIGITAL_PDF,
                page_count=None,
                readable=True,
                warnings=["PyMuPDF not installed; PDF page inspection is limited."],
                signals={"pymupdf": False},
            )

        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception:  # noqa: BLE001
            return InspectResult(
                content_kind=DocumentContentKind.UNREADABLE,
                page_count=None,
                readable=False,
                error_code="corrupt_pdf",
                error_message="PDF could not be opened (corrupt or truncated).",
            )

        try:
            if doc.is_encrypted:
                # Try empty password; if still locked, reject
                if not doc.authenticate(""):
                    return InspectResult(
                        content_kind=DocumentContentKind.UNREADABLE,
                        page_count=doc.page_count,
                        encrypted=True,
                        readable=False,
                        error_code="pdf_encrypted",
                        error_message="PDF is password-protected and cannot be processed without a password.",
                    )

            n = doc.page_count
            if n == 0:
                return InspectResult(
                    content_kind=DocumentContentKind.UNREADABLE,
                    page_count=0,
                    readable=False,
                    error_code="pdf_zero_pages",
                    error_message="PDF contains zero pages.",
                )

            text_pages = 0
            empty_pages = 0
            for i in range(min(n, 50)):
                page = doc.load_page(i)
                text = (page.get_text("text") or "").strip()
                if len(text) >= MIN_TEXT_CHARS_PER_PAGE:
                    text_pages += 1
                else:
                    empty_pages += 1

            if text_pages == 0:
                kind = DocumentContentKind.SCANNED_PDF
            elif empty_pages == 0:
                kind = DocumentContentKind.DIGITAL_PDF
            else:
                kind = DocumentContentKind.MIXED_PDF

            warnings: list[str] = []
            if n > 50:
                warnings.append(f"PDF has {n} pages; inspection sampled first 50.")

            return InspectResult(
                content_kind=kind,
                page_count=n,
                encrypted=False,
                readable=True,
                warnings=warnings,
                signals={
                    "text_pages_sampled": text_pages,
                    "empty_pages_sampled": empty_pages,
                    "pymupdf": True,
                },
            )
        finally:
            doc.close()
