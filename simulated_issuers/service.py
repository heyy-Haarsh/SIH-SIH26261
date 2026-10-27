"""Shared fixture lookup + response builder for all issuer routers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Lookup key field preferred for each fixture file
FIXTURE_KEY_FIELDS: dict[str, list[str]] = {
    "fire_safety": ["certificate_number", "reference_number"],
    "building_occupancy": ["certificate_number", "reference_number", "registration_number"],
    "structural_engineer": ["engineer_registration_number", "membership_number", "registration_number"],
    "aicte_payment": ["transaction_id", "receipt_number"],
    "icai_membership": ["auditor_registration_number", "membership_number", "ca_membership_number"],
    "affidavit_estamp": ["stamp_paper_ref", "estamp_number"],
}

PROVIDER_NAMES: dict[str, str] = {
    "fire_safety": "[SIMULATED] Fire Safety Authority",
    "building_occupancy": "[SIMULATED] Building / Occupancy Authority",
    "structural_engineer": "[SIMULATED] Structural Engineer Registry",
    "aicte_payment": "[SIMULATED] AICTE Payment Portal",
    "icai_membership": "[SIMULATED] ICAI Membership Portal",
    "affidavit_estamp": "[SIMULATED] Affidavit E-Stamp Registry",
}

SCOPE: dict[str, str] = {
    "fire_safety": "certificate number exists in fixture registry",
    "building_occupancy": "occupancy certificate number exists in fixture registry",
    "structural_engineer": "engineer registration exists in fixture registry",
    "aicte_payment": "transaction id exists in fixture registry",
    "icai_membership": "membership number exists in fixture registry",
    "affidavit_estamp": "stamp paper / e-stamp ref exists in fixture registry",
}


@lru_cache(maxsize=16)
def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def clear_fixture_cache() -> None:
    load_fixture.cache_clear()


def resolve_lookup_key(fixture_name: str, payload: dict[str, Any]) -> str:
    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
    for key in FIXTURE_KEY_FIELDS.get(fixture_name, []):
        val = (fields.get(key) or "").strip()
        if val:
            return val
    # common fallbacks
    for key in ("lookup_key", "id", "key"):
        val = (fields.get(key) or "").strip()
        if val:
            return val
    return ""


def build_response(fixture_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    fixtures = load_fixture(fixture_name)
    lookup = resolve_lookup_key(fixture_name, payload)
    entry = fixtures.get(lookup) or fixtures.get("_default") or {"status": "verification_pending"}
    status = entry.get("status", "verification_pending")
    ref = f"SIM-{fixture_name.upper().replace('_', '-')}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matched = [k for k in FIXTURE_KEY_FIELDS.get(fixture_name, []) if (payload.get("fields") or payload).get(k)]
    if not matched and lookup:
        matched = ["lookup_key"]
    mismatched = list(entry.get("mismatched_fields") or [])
    expiry = entry.get("expiry")
    summary = f"Found: {status}" + (f", expiry {expiry}" if expiry else "")
    return {
        "simulated": True,
        "reference_id": ref,
        "timestamp": now,
        "status": status,
        "scope_of_confirmation": SCOPE.get(fixture_name, "fixture registry lookup"),
        "mode": "SIMULATED",
        "official_verification": False,
        "provider_name": PROVIDER_NAMES.get(fixture_name, f"[SIMULATED] {fixture_name}"),
        "provider_reference_id": ref,
        "request_summary": f"Queried key={lookup or '(empty)'}",
        "response_summary": summary,
        "matched_fields": matched,
        "mismatched_fields": mismatched,
        "detail": "[SIMULATED] This result is not an official verification",
        "expiry": expiry,
        "lookup_key": lookup,
    }
