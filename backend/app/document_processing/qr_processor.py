"""QR decode + field comparison (optional pyzbar). Degrades if missing."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("praman.qr")


@dataclass
class QRCheckResult:
    status: str  # match | mismatch | payload_unreadable | qr_absent
    payload_raw: Optional[str] = None
    payload_fields: dict[str, str] = field(default_factory=dict)
    matched_fields: list[str] = field(default_factory=list)
    mismatched_fields: list[str] = field(default_factory=list)
    detail: str = ""


def _parse_payload(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v is not None}
    except json.JSONDecodeError:
        pass
    out: dict[str, str] = {}
    for part in re.split(r"[;\n|&]", raw):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        elif ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def decode_qr_from_image_bytes(image_bytes: bytes) -> list[str]:
    try:
        from pyzbar.pyzbar import decode as zbar_decode  # type: ignore
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        codes = zbar_decode(img)
        return [c.data.decode("utf-8", errors="replace") for c in codes]
    except ImportError:
        logger.info("pyzbar/Pillow unavailable — QR decode skipped")
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("QR decode failed: %s", exc)
        return []


def compare_qr_to_fields(
    payloads: list[str],
    extracted: dict[str, str],
) -> QRCheckResult:
    if not payloads:
        return QRCheckResult(status="qr_absent", detail="No QR codes detected")
    raw = payloads[0]
    fields = _parse_payload(raw)
    if not fields:
        return QRCheckResult(
            status="payload_unreadable",
            payload_raw=raw,
            detail="QR payload could not be parsed as fields",
        )
    matched: list[str] = []
    mismatched: list[str] = []
    for k, v in fields.items():
        key = k.strip().lower().replace(" ", "_")
        # also try original key
        ev = extracted.get(key) or extracted.get(k)
        if ev is None:
            continue
        if ev.strip().casefold() == v.strip().casefold():
            matched.append(key)
        else:
            mismatched.append(key)
    if mismatched:
        status = "mismatch"
    elif matched:
        status = "match"
    else:
        status = "payload_unreadable"
        detail = "QR fields did not overlap with extracted fields"
        return QRCheckResult(
            status=status,
            payload_raw=raw,
            payload_fields=fields,
            matched_fields=matched,
            mismatched_fields=mismatched,
            detail=detail,
        )
    return QRCheckResult(
        status=status,
        payload_raw=raw,
        payload_fields=fields,
        matched_fields=matched,
        mismatched_fields=mismatched,
        detail=f"QR {status}: matched={matched} mismatched={mismatched}",
    )


class QRProcessor:
    name = "qr_processor"

    def check(
        self,
        *,
        image_bytes_list: list[bytes],
        extracted_fields: dict[str, str],
    ) -> QRCheckResult:
        payloads: list[str] = []
        for img in image_bytes_list:
            payloads.extend(decode_qr_from_image_bytes(img))
        return compare_qr_to_fields(payloads, extracted_fields)
