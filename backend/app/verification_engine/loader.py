"""Load document-type verification configs from JSON files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent / "configs"


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict[str, Any]]:
    by_requirement: dict[str, dict[str, Any]] = {}
    for path in sorted(CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        req = str(data.get("requirement_code") or data.get("code") or "").strip().upper()
        if not req:
            continue
        data["_config_path"] = path.name
        by_requirement[req] = data
    return by_requirement


def list_configs() -> list[dict[str, Any]]:
    return list(_load_all().values())


def get_config_for_requirement(requirement_code: str) -> dict[str, Any] | None:
    return _load_all().get((requirement_code or "").strip().upper())


def clear_config_cache() -> None:
    _load_all.cache_clear()
