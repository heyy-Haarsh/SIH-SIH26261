"""PDFTextExtractor — page-by-page digital text via PyMuPDF."""

from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.document_processing.intelligence_types import PageText

MIN_USABLE_CHARS = 40


def _fitz():
    try:
        import fitz

        return fitz
    except ImportError:
        return None


class PDFTextExtractor:
    name = "pdf_text_extractor"

    def available(self) -> bool:
        return _fitz() is not None and get_settings().enable_local_pdf_extraction

    def extract_pages(self, content: bytes, *, max_pages: Optional[int] = None) -> list[PageText]:
        fitz = _fitz()
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed")

        settings = get_settings()
        limit = max_pages if max_pages is not None else settings.max_extraction_pages
        doc = fitz.open(stream=content, filetype="pdf")
        pages: list[PageText] = []
        try:
            if doc.is_encrypted and not doc.authenticate(""):
                raise PermissionError("pdf_encrypted")
            n = min(doc.page_count, limit)
            for i in range(n):
                page = doc.load_page(i)
                # Normalize rotation for consistent coordinates
                rot = page.rotation
                text = page.get_text("text") or ""
                blocks_raw = page.get_text("dict").get("blocks", [])
                blocks: list[dict] = []
                for b in blocks_raw:
                    if b.get("type") != 0:
                        continue
                    bbox = b.get("bbox")
                    line_text = []
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            line_text.append(span.get("text", ""))
                    joined = " ".join(line_text).strip()
                    if joined and bbox:
                        blocks.append(
                            {
                                "text": joined,
                                "bbox": list(bbox),
                                "coordinate_space": "pdf_page_points",
                            }
                        )
                pages.append(
                    PageText(
                        page_number=i + 1,
                        text=text,
                        source="pdf_text" if len(text.strip()) >= MIN_USABLE_CHARS else "none",
                        char_count=len(text.strip()),
                        rotation=rot,
                        width=float(page.rect.width),
                        height=float(page.rect.height),
                        blocks=blocks,
                    )
                )
        finally:
            doc.close()
        return pages
