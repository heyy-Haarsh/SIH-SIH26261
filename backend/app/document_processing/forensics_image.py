"""ELA and perceptual hash helpers (optional imagehash/Pillow)."""

from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger("praman.forensics_image")


def ela_anomaly_score(image_bytes: bytes, *, quality: int = 95, threshold: float = 15.0) -> float:
    """Return 0–1 anomaly score from Error Level Analysis. Degrades to 0 if Pillow missing."""
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return 0.0
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")
        diff = ImageChops.difference(original, resaved)
        stat = ImageStat.Stat(diff)
        mean = sum(stat.mean) / max(len(stat.mean), 1)
        # Map mean difference to 0–1
        return max(0.0, min(1.0, mean / max(threshold, 1e-6)))
    except Exception as exc:  # noqa: BLE001
        logger.info("ELA skipped: %s", exc)
        return 0.0


def phash_hex(image_bytes: bytes) -> Optional[str]:
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        # Fallback: crude average hash via Pillow only
        try:
            from PIL import Image
            import hashlib

            img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((8, 8))
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p >= avg else "0" for p in pixels)
            return hashlib.sha256(bits.encode()).hexdigest()[:16]
        except Exception:  # noqa: BLE001
            return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return str(imagehash.phash(img))
    except Exception as exc:  # noqa: BLE001
        logger.info("pHash skipped: %s", exc)
        return None


def hamming_distance_hex(a: str, b: str) -> int:
    if not a or not b:
        return 64
    # imagehash strings are hex-like; compare bit difference on bytes
    try:
        ia = int(a, 16)
        ib = int(b, 16)
        return (ia ^ ib).bit_count()
    except ValueError:
        return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
