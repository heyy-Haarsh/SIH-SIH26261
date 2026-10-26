"""OCRProcessor — Tesseract via pytesseract, with honest availability reporting."""

from __future__ import annotations

import io
import logging
from typing import Optional

from app.core.config import get_settings
from app.document_processing.intelligence_types import PageText

logger = logging.getLogger("praman.ocr")


def tesseract_status() -> dict:
    """Detect Tesseract executable and configured languages without requiring OCR to succeed."""
    settings = get_settings()
    wanted = [x.strip() for x in settings.ocr_languages.split(",") if x.strip()]
    status = {
        "enabled": settings.enable_local_ocr,
        "pytesseract_installed": False,
        "tesseract_cmd_found": False,
        "tesseract_version": None,
        "languages_requested": wanted,
        "languages_available": [],
        "languages_missing": wanted[:],
        "available": False,
        "message": "",
    }
    if not settings.enable_local_ocr:
        status["message"] = "Local OCR is disabled (ENABLE_LOCAL_OCR=false)."
        return status

    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError

        status["pytesseract_installed"] = True
        try:
            ver = pytesseract.get_tesseract_version()
            status["tesseract_cmd_found"] = True
            status["tesseract_version"] = str(ver)
        except TesseractNotFoundError:
            status["message"] = (
                "Tesseract executable not found. Install Tesseract OCR and ensure it is on PATH."
            )
            return status
        except Exception as exc:  # noqa: BLE001
            status["message"] = f"Could not query Tesseract version: {exc.__class__.__name__}"
            return status

        try:
            langs = pytesseract.get_languages(config="")
            status["languages_available"] = sorted(langs)
            missing = [l for l in wanted if l not in langs]
            status["languages_missing"] = missing
            if missing:
                status["message"] = (
                    f"Tesseract language data missing for: {', '.join(missing)}. "
                    f"Available: {', '.join(sorted(langs)[:20])}."
                )
                status["available"] = False
            else:
                status["available"] = True
                status["message"] = f"OCR ready (langs={','.join(wanted)})."
        except Exception as exc:  # noqa: BLE001
            status["message"] = f"Could not list Tesseract languages: {exc.__class__.__name__}"
        return status
    except ImportError:
        status["message"] = "pytesseract package is not installed."
        return status


class OCRProcessor:
    name = "ocr_processor"

    def __init__(self) -> None:
        self._status = tesseract_status()

    @property
    def available(self) -> bool:
        return bool(self._status.get("available"))

    @property
    def status(self) -> dict:
        return dict(self._status)

    def ocr_pil_image(self, image, *, page_number: int = 1) -> PageText:
        """OCR a PIL image. Raises RuntimeError if OCR is unavailable."""
        if not self.available:
            raise RuntimeError(self._status.get("message") or "ocr_unavailable")

        import pytesseract
        from PIL import Image

        settings = get_settings()
        langs = "+".join(x.strip() for x in settings.ocr_languages.split(",") if x.strip()) or "eng"

        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Orientation: use OSD when available; ignore failures
        try:
            osd = pytesseract.image_to_osd(image)
            for line in osd.splitlines():
                if "Rotate:" in line:
                    degrees = int(line.split(":")[-1].strip())
                    if degrees and degrees % 360 != 0:
                        image = image.rotate(360 - degrees, expand=True)
                    break
        except Exception:  # noqa: BLE001
            pass

        data = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT)
        words = []
        confs = []
        blocks = []
        n = len(data.get("text", []))
        for i in range(n):
            txt = (data["text"][i] or "").strip()
            conf = float(data["conf"][i]) if data["conf"][i] != "-1" else None
            if not txt:
                continue
            words.append(txt)
            if conf is not None and conf >= 0:
                confs.append(conf / 100.0)
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            blocks.append(
                {
                    "text": txt,
                    "bbox": [float(x), float(y), float(x + w), float(y + h)],
                    "coordinate_space": "image_pixels",
                    "confidence": (conf / 100.0) if conf is not None and conf >= 0 else None,
                }
            )

        mean_conf = sum(confs) / len(confs) if confs else None
        text = " ".join(words)
        return PageText(
            page_number=page_number,
            text=text,
            source="ocr",
            char_count=len(text),
            ocr_confidence=mean_conf,
            width=float(image.width),
            height=float(image.height),
            blocks=blocks,
        )

    def ocr_pdf_page(self, content: bytes, page_index: int, *, page_number: int) -> PageText:
        """Render one PDF page via PyMuPDF and OCR it."""
        if not self.available:
            raise RuntimeError(self._status.get("message") or "ocr_unavailable")

        import fitz
        from PIL import Image

        settings = get_settings()
        dpi = max(72, min(settings.ocr_dpi, 400))
        zoom = dpi / 72.0
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            page = doc.load_page(page_index)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            result = self.ocr_pil_image(img, page_number=page_number)
            # Convert image-pixel bboxes toward PDF points approximately
            scale = 72.0 / dpi
            converted = []
            for b in result.blocks:
                x0, y0, x1, y1 = b["bbox"]
                converted.append(
                    {
                        **b,
                        "bbox": [x0 * scale, y0 * scale, x1 * scale, y1 * scale],
                        "coordinate_space": "pdf_page_points",
                    }
                )
            result.blocks = converted
            result.width = float(page.rect.width)
            result.height = float(page.rect.height)
            return result
        finally:
            doc.close()

    def ocr_image_bytes(self, content: bytes) -> PageText:
        from PIL import Image

        img = Image.open(io.BytesIO(content))
        img.load()
        return self.ocr_pil_image(img, page_number=1)
