"""Shared text helpers used by rules and extraction pipelines."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y")


def parse_date(value: str) -> Optional[date]:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def field_label(field_name: str) -> str:
    return field_name.replace("_", " ").title()
