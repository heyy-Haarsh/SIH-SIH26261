"""Deterministic readability checks. Separate from authenticity and from rule results.

This does not use a trained quality model. It measures whether an image is blank, tiny, or
so smooth that text is unlikely to be readable, and it reports that reason in plain language.
Text-based files are not judged here — missing text is already reported by the extractor.
"""

from __future__ import annotations

import io
from typing import Optional

from app.models.enums import DocumentContentKind

# Mean adjacent-pixel difference on a 256px preview. Smooth/blurred scans sit well below this;
# a sharp checkerboard or printed text sits well above it. Tuned on synthetic images in tests,
# not on a labelled scan corpus.
_BLUR_ENERGY = 6.0
_BLANK_STDEV = 8.0
_MIN_SHORT_SIDE = 200


def assess_upload(
    content: bytes,
    kind: DocumentContentKind,
    *,
    pages_with_text: int = 0,
) -> Optional[str]:
    """Return a ``clarity:<level>:<message>`` warning, or None when the file looks readable
    or when this check does not apply."""
    try:
        if kind == DocumentContentKind.IMAGE:
            return _format(_assess_image_bytes(content))
        if kind == DocumentContentKind.SCANNED_PDF and pages_with_text == 0:
            return _format(_assess_pdf_first_page(content))
    except Exception:  # noqa: BLE001 — a quality probe must not fail the upload
        return None
    return None


def _format(result: Optional[dict]) -> Optional[str]:
    if not result or result["level"] == "clear":
        return None
    return f"clarity:{result['level']}:{result['message']}"


def _assess_image_bytes(content: bytes) -> Optional[dict]:
    from PIL import Image

    img = Image.open(io.BytesIO(content))
    img.load()
    return _assess_image(img)


def _assess_pdf_first_page(content: bytes) -> Optional[dict]:
    import fitz
    from PIL import Image

    doc = fitz.open(stream=content, filetype="pdf")
    try:
        if doc.page_count < 1:
            return {
                "level": "unreadable",
                "message": "The PDF has no pages.",
            }
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return _assess_image(img)
    finally:
        doc.close()


def _assess_image(img) -> dict:
    width, height = img.size
    short = min(width, height)
    if short < _MIN_SHORT_SIDE:
        return {
            "level": "unclear",
            "message": (
                f"The image is very small ({width}×{height} px). "
                "Upload a larger, sharper copy with the whole page visible."
            ),
        }

    energy, stdev = _edge_stats(img)
    if stdev < _BLANK_STDEV:
        return {
            "level": "unreadable",
            "message": "The image looks blank or is a single flat colour, so there is no text to read.",
        }
    if energy < _BLUR_ENERGY:
        return {
            "level": "unclear",
            "message": (
                "The image looks blurred or out of focus, so the text may not be readable. "
                "Upload a sharper scan or photo."
            ),
        }
    return {"level": "clear", "message": "The image has enough detail to read."}


def _edge_stats(img) -> tuple[float, float]:
    gray = img.convert("L")
    w, h = gray.size
    px = list(gray.getdata())
    if w < 8 or h < 8 or not px:
        return 0.0, 0.0
    # Step across the original pixels. Resampling would blur a sharp pattern into gray
    # and then report that the sharp image was unreadable.
    step = max(1, max(w, h) // 256)
    diffs: list[int] = []
    for y in range(0, h, step):
        row = y * w
        for x in range(0, w - step, step):
            diffs.append(abs(px[row + x] - px[row + x + step]))
    for y in range(0, h - step, step):
        for x in range(0, w, step):
            diffs.append(abs(px[y * w + x] - px[(y + step) * w + x]))
    energy = (sum(diffs) / len(diffs)) if diffs else 0.0
    mean = sum(px) / len(px)
    var = sum((p - mean) ** 2 for p in px) / len(px)
    return energy, var ** 0.5
