# PRAMAN — Implementation Plan (v2.1, decisions locked)
**SIH26261 · Plan Date:** 2026-10-27 · **Decisions locked:** 2026-10-27

> **Before reading this plan:** see [AUDIT.md](./AUDIT.md) for the current state of every module.
> Open questions Q1–Q7 are **resolved** below; implementation may proceed phase-by-phase for review.

---

## Guiding Principles (preserved from spec)

1. **Config-driven:** adding a document type = one JSON config + (optionally) one connector.
2. **LLM is fallback only:** deterministic code makes all pass/fail decisions.
3. **Three statuses are always separate:** `rule_validation_status`, `external_verification_status`, `review_status`.
4. **Never claim verified from unavailable source.**
5. **Degrade gracefully** when LLM / OCR / external connector fails.
6. **All forensics outputs:** "preliminary indicator requiring human verification" — never "forged".
7. **REAL vs SIMULATED clearly labelled everywhere:** code, logs, API responses, UI payloads, PDF reports.
8. **`official_verification: false` whenever `mode == SIMULATED`** — enforced at model level, never overridable by a connector.

---

## Architecture Decision Record (to be moved to DECISIONS.md on approval)

| ID | Decision | Rationale |
|----|----------|-----------|
| D-01 | Keep existing `verification_engine/pipeline.py` as the three-layer orchestrator; extend, not replace. | It already correctly separates the three statuses. |
| D-02 | Keep existing `verification_engine/configs/*.json` schema; add new fields (`aph_clause`, `source_note`, `arithmetic_checks`, `conditional_checks`). | Backward-compatible extension. |
| D-03 | ~~Replace `integrations/mock_adapter.py` with fixture-backed mock connectors~~ → **Superseded by D-11.** Fixture-backed connectors now run inside the simulated issuer service, called over HTTP. | Addendum §4 replaces direct function stubs with a real HTTP service. |
| D-04 | Add `pyHanko` for PDF digital signature chain validation as optional dependency (falls back to sigflags if not installed). | Spec requires pyHanko. |
| D-05 | Add `pyzbar` + `opencv-python-headless` for QR decode and ELA/copy-move forensics. | Spec requires QR decode and image forensics. |
| D-06 | Add `rapidfuzz` for fuzzy string matching / transliteration in reconciliation. | Spec requires fuzzy matching with thresholds from config. |
| D-07 | Use **WeasyPrint** (HTML → PDF) with a single Jinja2 template for scrutiny reports (Stage 8). No mandated AICTE layout. | Clean professional output; restylable in one template file (Q3). |
| D-08 | Implement hash-chained audit log as a separate append-only table `audit_chain_events`, separate from `AuditEvents`. | Separation of concerns; existing AuditEvent is fine for human-readable log. |
| D-09 | Pydantic `ExtractedField`, `Finding`, `Evidence`, `DocumentResult`, `ApplicationResult` models live in `app/schemas/engine.py`. They are NOT ORM models — they are data-transfer objects produced by the pipeline and serialized to JSON/PDF. | Separation from ORM reduces coupling. |
| D-10 | Synthetic dataset generator lives in `tests/synthetic/` and is independent of the test suite so it can be run as a standalone script. | Spec requires it to be runnable end-to-end. |
| D-11 | **Simulated issuer service** is a separate FastAPI app in `simulated_issuers/`. Default bind port **8001**, configurable via `.env` (`SIMULATED_ISSUERS_PORT`, `SIMULATED_ISSUERS_URL`). If the port is busy at startup, **fail with a clear error** — never silently switch ports. Main app calls it over HTTP only. | Addendum §4 + Q6. |
| D-12 | **Connector registry** is a single YAML config file (`verification_engine/configs/connector_registry.yaml`) that maps each document type to `connector_name`, `mode`, `timeout_seconds`, `retries`, `fallback_status`. Switching real↔simulated requires only config + `.env` credentials, never a code change. | Addendum §3. |
| D-13 | **`VerificationResult` / `AdapterResult`** must carry `mode: REAL\|SIMULATED`, `official_verification: bool`, `provider_name`, `provider_reference_id`, `timestamp`, `request_summary`, `response_summary`, `scope_of_confirmation`. The field `official_verification` is set to `false` by the model validator whenever `mode == SIMULATED` — connectors cannot override it. | Addendum §2. |
| D-14 | **Affidavit 2** document config is added as `verification_engine/configs/affidavit_2.json`. All `aph_clause` values are `TODO: fill from APH §X.Y`. | Addendum §1. |
| D-15 | **Real integrations** are documented in `docs/INTEGRATION_RESEARCH.md` but only implemented if the API is public, documented, authorized, and credentials are available. Otherwise a stub adapter returns `source_unavailable` with a clear reason string. No scraping, no CAPTCHA bypass. | Addendum §5. |
| D-16 | **LLM:** Generic `LLMExtractor` interface; `LLM_PROVIDER=gemini\|openai\|none` in `.env`. Default adapter = Gemini; second = OpenAI; `none` skips LLM and uses OCR + regex only. LLM used only for classification fallback, structured field extraction (strict JSON schema), and explanation text — **never pass/fail**. | Q1. |
| D-17 | **pyHanko trust store:** `TRUST_STORE_DIR` in `.env` (empty by default). No CCA India bundle is shipped. If signed PDF + no trust roots: verify integrity / modification-after-signing for real; report `chain_untrusted_no_trust_store`; set `external_verification_status` to `manual_review_required` with limitation in the report. Scanned signatures/stamps → signature check `not_applicable`. Document CCA download steps in `docs/INTEGRATION_RESEARCH.md` — never invent or bundle certs. | Q2. |
| D-18 | **PDF report:** Clean professional HTML → PDF. Templated sections (header, application summary, rule-set version, per-document findings with evidence/page refs, signature status, REAL/SIMULATED labels, cross-document findings, recommended actions, reviewer sign-off). Permanent notice: *"Decision-support output; final decision rests with the competent authority."* Single template file for restyling. | Q3. |
| D-19 | **Phase ordering:** **Sequential.** Review and test each phase before the next starts. Phases 3 and 4 remain independent logically; implementation is sequential. Parallelization allowed only for writing tests, not implementation. | Q4. |
| D-20 | **Transliteration:** Apply in **both** extraction and reconciliation. Extraction stores raw value unchanged + separate `normalized_value`. Reconciliation compares normalized values + fuzzy matching (config thresholds) and shows **both** original and normalized forms in evidence. | Q5. |
| D-21 | **Circuit breaker:** `tenacity` for retry/backoff + a small **manual** state machine (`closed` / `open` / `half-open`) with configurable failure threshold and cooldown. Do **not** add the `circuitbreaker` library. Unit-test transitions. Open circuit or timeout → `source_unavailable`, never a crash. | Q7. |

---

## Phase Overview

```
Phase 0  — Hardening & Cleanup               (no new features; prerequisite)
Phase 0b — Affidavit 2 Config + Research Docs (new doc type; INTEGRATION_RESEARCH.md)
Phase 1  — Pydantic Core Data Model + VerificationResult v2
Phase 2  — Simulated Issuer Service + Connector Registry
Phase 3  — Enhanced Extraction               (LLM, QR, Hindi/Mar OCR)
Phase 4  — pyHanko PKI Chain + Config Extensions (arithmetic, conditional)
Phase 5  — Forensics Triage Score + Enhanced Forensics (ELA, pHash, hidden text)
Phase 6  — Fuzzy Reconciliation + Transliteration
Phase 7  — Hash-chained Audit Log
Phase 8  — Reports: JSON + PDF              (REAL/SIMULATED labels; no implied authenticity)
Phase 9  — Synthetic Dataset + Evaluation Harness
Phase 10 — Final Integration + README       (DoD check)
```

**Ordering (D-19):** Phases run **sequentially**. Review and test each phase before starting the next. Phases 3 and 4 are independent logically, but implementation is not parallelized. Writing tests for a later phase may proceed in parallel; implementation code may not.

**Each phase ends with: all existing tests still pass + new phase tests pass + short real command output shown.**

---

## Phase 0 — Hardening & Cleanup

**Goal:** Make the repo safe and coherent before adding features.

### 0.1 Gitignore cleanup
- Add `praman_dev.db`, `tests/test_praman.db`, `backend/uploads/` to `.gitignore`.

### 0.2 Resolve dual extraction path
- Remove `document_processing/extraction.py` `LocalExtractionModule` (superseded by `orchestrator.py` / `field_extractor.py`).
- Update any imports in `validation_service.py` that still use the old path.

### 0.3 Semantic category coverage
- Add `AICTE_PAYMENT_RECEIPT`, `AUDITED_ACCOUNTS`, `STRUCTURAL_STABILITY`, `SATELLITE_MAP` to `SemanticDocumentCategory` enum and `SemanticDocumentClassifier` keyword maps.

### 0.4 Dependency audit
- Pin `requirements.txt` with exact versions; split into `requirements.txt` (production) and `requirements-dev.txt` (test/lint/eval).

### Files changed
| File | Change |
|------|--------|
| `.gitignore` | Add db + uploads |
| `backend/app/document_processing/extraction.py` | Delete (superseded) |
| `backend/app/models/enums.py` | Add 4 categories to `SemanticDocumentCategory` |
| `backend/app/document_processing/semantic_classifier.py` | Add keyword maps for 4 new categories |
| `backend/requirements.txt` | Pin versions |
| `backend/requirements-dev.txt` | New file |

### Tests
- `tests/test_inspector_classifier.py`: add assertions that new categories classify correctly.

---

## Phase 0b — Affidavit 2 Config + Integration Research

**Goal:** Add the Affidavit 2 document type (with TODO placeholders) and document all real-API integration research findings. No connectors implemented yet — research only.

### 0b.1 Affidavit 2 document config (new)

New file: `backend/app/verification_engine/configs/affidavit_2.json`

```json
{
  "version": "v1",
  "document_type": "AFFIDAVIT_2",
  "display_name": "Affidavit 2",
  "source_note": "SYNTHETIC",
  "layer1": {
    "required_fields": [
      {"field": "institution_name",    "aph_clause": "TODO: fill from APH §X.Y", "severity": "failed"},
      {"field": "signatory_name",      "aph_clause": "TODO: fill from APH §X.Y", "severity": "failed"},
      {"field": "signatory_designation","aph_clause": "TODO: fill from APH §X.Y", "severity": "failed"},
      {"field": "execution_date",      "aph_clause": "TODO: fill from APH §X.Y", "severity": "failed"},
      {"field": "execution_place",     "aph_clause": "TODO: fill from APH §X.Y", "severity": "warning"},
      {"field": "stamp_paper_ref",     "aph_clause": "TODO: fill from APH §X.Y", "severity": "failed"},
      {"field": "notary_details",      "aph_clause": "TODO: fill from APH §X.Y", "severity": "warning"}
    ],
    "date_rules": [
      {
        "id": "EXEC_DATE_NOT_FUTURE",
        "description": "Execution date must not be in the future",
        "field": "execution_date",
        "op": "lte",
        "compare_to": "today",
        "severity": "failed",
        "aph_clause": "TODO: fill from APH §X.Y"
      }
    ],
    "format_checks": [
      {
        "id": "STAMP_REF_FORMAT",
        "description": "Stamp paper or e-stamp reference format",
        "field": "stamp_paper_ref",
        "regex": "TODO: insert stamp ref regex",
        "severity": "warning",
        "aph_clause": "TODO: fill from APH §X.Y"
      }
    ],
    "arithmetic_checks": [],
    "conditional_checks": []
  },
  "layer2": {
    "connector": "affidavit_estamp_connector",
    "fields_to_verify": ["stamp_paper_ref", "notary_details"]
  },
  "extraction_hints": {
    "page_references": true,
    "fields": {
      "institution_name":       {"aliases": ["संस्था का नाम", "संस्थेचे नाव"]},
      "signatory_name":         {"aliases": ["हस्ताक्षरकर्ता", "स्वाक्षरकर्त्याचे नाव"]},
      "signatory_designation":  {"aliases": ["पदनाम"]},
      "execution_date":         {"aliases": ["तारीख"]},
      "execution_place":        {"aliases": ["स्थान"]},
      "stamp_paper_ref":        {"aliases": ["मुद्रांक", "e-stamp"]},
      "notary_details":         {"aliases": ["नोटरी"]},
      "page_references":        {"aliases": []}
    }
  }
}
```

### 0b.2 Field aliases in field_extractor.py
- Add extraction aliases for all Affidavit 2 fields to `backend/app/document_processing/field_extractor.py`.

### 0b.3 `AFFIDAVIT_2` in SemanticDocumentCategory
- Add `AFFIDAVIT_2` to `models/enums.py` and keyword map in `semantic_classifier.py`.

### 0b.4 `docs/INTEGRATION_RESEARCH.md` (new)

Research-only document. For each potential real API, record:
- What is publicly documented
- Whether registration/access is required and how
- Feasibility assessment for a student team
- Stub adapter placeholder and `source_unavailable` reason string
- Whether a real adapter will be implemented (yes only if API is documented + authorized + credentials provided)

APIs to research: **DigiLocker, API Setu, AICTE payment portal, fire safety authority, building/occupancy authority, structural engineer registry (NSET / state council), ICAI membership portal.**

Also document **CCA India PKI trust roots** (D-17 / Q2):
- Official CCA India root certificates must be downloaded from the **official CCA India source** and placed in the folder pointed to by `TRUST_STORE_DIR`.
- Do **not** bundle, invent, or embed any certificates in the repo.
- Until operators add roots, signed PDFs use integrity checks only and report `chain_untrusted_no_trust_store` / `manual_review_required`.

> **Hard rules:** no scraping, no CAPTCHA bypass, no terms-of-use violation. If the API requires registration that the team does not have, the adapter returns `source_unavailable` with reason `"API access requires institutional registration; credentials not provided"`.

### Files changed
| File | Change |
|------|--------|
| `backend/app/verification_engine/configs/affidavit_2.json` | **NEW** |
| `backend/app/models/enums.py` | Add `AFFIDAVIT_2` to `SemanticDocumentCategory` |
| `backend/app/document_processing/semantic_classifier.py` | Add keyword map for `AFFIDAVIT_2` |
| `backend/app/document_processing/field_extractor.py` | Add Affidavit 2 field aliases |
| `docs/INTEGRATION_RESEARCH.md` | **NEW** (research stubs) |

### Tests
- `tests/test_inspector_classifier.py`: assert `AFFIDAVIT_2` classifies correctly.
- `tests/test_layer1_affidavit2.py`: required-field checks, date rule, format check all produce expected statuses.

---

## Phase 1 — Pydantic Core Data Model + VerificationResult v2

**Goal:** Implement spec-compliant Pydantic v2 models including the updated `VerificationResult` fields from the addendum.

### 1.1 `app/schemas/engine.py` — core output DTOs

```python
from pydantic import BaseModel, model_validator
from typing import Literal, Optional
from datetime import datetime
from enum import Enum

class VerificationMode(str, Enum):
    REAL = "REAL"
    SIMULATED = "SIMULATED"

class ExternalVerificationStatus(str, Enum):
    # Exactly the 6 PS literals — nothing else appears in any report or API response
    verified                 = "verified"
    mismatch_detected        = "mismatch_detected"
    expired                  = "expired"
    verification_pending     = "verification_pending"
    source_unavailable       = "source_unavailable"
    manual_review_required   = "manual_review_required"

class VerificationResultOut(BaseModel):
    status: ExternalVerificationStatus
    mode: VerificationMode
    official_verification: bool
    provider_name: str
    provider_reference_id: Optional[str]
    timestamp: datetime
    request_summary: str
    response_summary: str
    scope_of_confirmation: str   # e.g. "membership exists", NOT "document is genuine"
    matched_fields: list[str]
    mismatched_fields: list[str]
    source_url: Optional[str]
    raw_evidence_ref: Optional[str]

    @model_validator(mode="after")
    def enforce_official_false_for_simulated(self) -> "VerificationResultOut":
        if self.mode == VerificationMode.SIMULATED and self.official_verification:
            raise ValueError(
                "official_verification must be False when mode is SIMULATED"
            )
        return self

class ExtractedFieldOut(BaseModel):
    field_name: str
    value: str                      # raw extracted value — never overwritten
    normalized_value: Optional[str] # transliteration / ASCII form (D-20); separate field
    confidence: Optional[float]
    page: Optional[int]
    bbox: Optional[list[float]]      # [x0, y0, x1, y1]
    source: Literal["text_layer", "ocr", "llm", "filename_metadata"]
    raw_snippet: Optional[str]

class EvidenceOut(BaseModel):
    document_id: str
    page: Optional[int]
    bbox: Optional[list[float]]
    snippet: Optional[str]
    original_value: Optional[str]    # raw form shown in evidence (D-20)
    normalized_value: Optional[str]  # normalized form shown alongside original
    source: str

class FindingOut(BaseModel):
    id: str
    rule_id: str
    severity: str
    message: str
    evidence: list[EvidenceOut]
    clause_ref: str      # APH clause or "TODO: fill from handbook"
    confidence: Optional[float]

class SignalScoreOut(BaseModel):
    signal_code: str
    raw_score: float         # 0–1
    weight: float
    contribution: float      # raw_score × weight
    reason: str
    confidence: float
    evidence_region: Optional[str]
    interpretation: str      # always "preliminary indicator requiring human verification"

class TriageScoreOut(BaseModel):
    total: float             # 0–100
    signals: list[SignalScoreOut]
    interpretation: str      # always "preliminary indicator requiring human verification"
    config_version: str

class DocumentResultOut(BaseModel):
    document_id: str
    requirement_code: str
    document_type: str
    rule_validation_status: str        # pass | fail | partial | not_applicable
    external_verification_status: ExternalVerificationStatus
    review_status: str                 # not_required | pending_review | in_review | resolved
    signature_status: str              # e.g. "signed_valid" | "signed_chain_untrusted" | "not_applicable: scanned"
    findings: list[FindingOut]
    forensic_signals: list[SignalScoreOut]
    verification_results: list[VerificationResultOut]
    official_source_confirmed: bool    # false if all verification_results have official_verification==false

class ApplicationResultOut(BaseModel):
    application_id: str
    rule_set_version: str
    engine_version: str
    generated_at: datetime
    documents: list[DocumentResultOut]
    cross_doc_findings: list[FindingOut]
    triage_score_breakdown: TriageScoreOut
    overall_status: str
    report_disclaimer: str   # always states which results came from REAL vs SIMULATED sources
```

### 1.2 Serializers
- `app/services/serializers.py`: add `to_document_result_out()` and `to_application_result_out()`.

### 1.3 AdapterResult / VerificationResult internal type update
- `app/verification_engine/adapters/types.py`: extend `AdapterResult` with the new addendum fields:
  `mode`, `official_verification`, `provider_name`, `provider_reference_id`, `request_summary`, `response_summary`, `scope_of_confirmation`.
- The model validator from `VerificationResultOut` must be mirrored in `AdapterResult` so connectors cannot accidentally set `official_verification=True` for SIMULATED results.

### Files changed
| File | Change |
|------|--------|
| `app/schemas/engine.py` | **NEW** — core Pydantic models (v2, addendum-compliant) |
| `app/verification_engine/adapters/types.py` | Extend `AdapterResult` with v2 fields |
| `app/services/serializers.py` | Add mapping functions |
| `app/api/routes/doc_verification.py` | Return `DocumentResultOut` |

### Tests
- `tests/test_engine_models.py` (new):
  - Model construction and validation.
  - **(Addendum test b)** Assert `VerificationResultOut(mode=SIMULATED, official_verification=True, ...)` raises `ValidationError`.
  - Assert `ExternalVerificationStatus` rejects any value not in the 6 PS literals.

---

## Phase 2 — Simulated Issuer Service + Connector Registry

**Goal:** Stand up the separate FastAPI simulated-issuer service (addendum §4) and the connector registry config (addendum §3). Replace all direct mock function calls with HTTP calls through the connector interface.

### 2.1 Directory structure (new top-level package)

```
simulated_issuers/
├── __init__.py
├── main.py                     # FastAPI app, uvicorn entry point (SIMULATED_ISSUERS_PORT, default 8001)
├── config.py                   # settings (port, URL, latency, outage flag, rate limits)
├── routers/
│   ├── fire_safety.py          # POST /issuers/fire-safety/verify
│   ├── building_occupancy.py   # POST /issuers/building-occupancy/verify
│   ├── structural_engineer.py  # POST /issuers/structural-engineer/verify
│   ├── aicte_payment.py        # POST /issuers/aicte-payment/verify
│   ├── icai_membership.py      # POST /issuers/icai-membership/verify
│   └── affidavit_estamp.py     # POST /issuers/affidavit-estamp/verify
├── fixtures/
│   ├── fire_safety.json        # keyed by certificate_number; covers all 6 statuses
│   ├── building_occupancy.json
│   ├── structural_engineer.json
│   ├── aicte_payment.json      # keyed by transaction_id
│   ├── icai_membership.json    # keyed by membership_number
│   └── affidavit_estamp.json   # keyed by stamp_paper_ref
├── middleware/
│   ├── latency.py              # configurable sleep per request
│   └── outage.py              # FORCE_OUTAGE=true → 503 for all endpoints
└── requirements.txt            # fastapi, uvicorn, etc.
```

**Port binding (D-11 / Q6):** Default `SIMULATED_ISSUERS_PORT=8001`, URL via `SIMULATED_ISSUERS_URL` (e.g. `http://localhost:8001`). If the configured port is already in use at startup, **exit with a clear error** — do not silently pick another port.

### 2.2 Simulated issuer response schema

Every response from every endpoint:
```json
{
  "simulated": true,
  "reference_id": "SIM-FIRE-20261027-abc123",
  "timestamp": "2026-10-27T12:00:00Z",
  "status": "verified",
  "scope_of_confirmation": "certificate number exists in fixture registry",
  "mode": "SIMULATED",
  "official_verification": false,
  "provider_name": "[SIMULATED] Fire Safety Authority",
  "provider_reference_id": "SIM-FIRE-20261027-abc123",
  "request_summary": "Queried certificate_number=FIRE-2024-001",
  "response_summary": "Found: valid, expiry 2027-03-31",
  "matched_fields": ["certificate_number"],
  "mismatched_fields": [],
  "detail": "[SIMULATED] This result is not an official verification"
}
```

### 2.3 Fixture files — all 6 statuses

Each fixture file has at least one key triggering each of the 6 statuses:
```json
{
  "FIRE-VERIFIED-001":   {"status": "verified",               "expiry": "2028-01-01"},
  "FIRE-MISMATCH-001":   {"status": "mismatch_detected",      "mismatched_fields": ["institution_name"]},
  "FIRE-EXPIRED-001":    {"status": "expired",                "expiry": "2020-06-30"},
  "FIRE-PENDING-001":    {"status": "verification_pending"},
  "FIRE-UNAVAIL-001":    {"status": "source_unavailable"},
  "FIRE-MANUAL-001":     {"status": "manual_review_required"},
  "_default":            {"status": "verification_pending"}
}
```

### 2.4 Chaos / observability features
- `SIMULATED_LATENCY_MS=200` — base latency per request (configurable).
- `SIMULATED_LATENCY_JITTER_MS=100` — random jitter added to latency.
- `FORCE_OUTAGE=true` — forces all endpoints to return HTTP 503 (`source_unavailable`).
- `RANDOM_5XX_RATE=0.05` — probability (0–1) of injecting a random 500/502/503.
- `RATE_LIMIT_RPM=60` — requests per minute per endpoint (429 if exceeded).

### 2.5 Connector registry config

New file: `backend/app/verification_engine/configs/connector_registry.yaml`

```yaml
version: v1
connectors:
  fire_safety_certificate:
    connector_name: SimulatedFireSafetyConnector
    mode: simulated                                   # change to real + set env to switch
    base_url_env: FIRE_ISSUER_BASE_URL                # env var pointing to real or simulated URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  building_permission:
    connector_name: SimulatedBuildingOccupancyConnector
    mode: simulated
    base_url_env: BUILDING_ISSUER_BASE_URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  structural_stability:
    connector_name: SimulatedStructuralEngineerConnector
    mode: simulated
    base_url_env: STRUCTURAL_ISSUER_BASE_URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  aicte_payment_receipt:
    connector_name: SimulatedAICTEPaymentConnector
    mode: simulated
    base_url_env: AICTE_PAYMENT_ISSUER_BASE_URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  audited_accounts:
    connector_name: SimulatedICAIMembershipConnector
    mode: simulated
    base_url_env: ICAI_ISSUER_BASE_URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  affidavit_2:
    connector_name: SimulatedAffidavitEStampConnector
    mode: simulated
    base_url_env: ESTAMP_ISSUER_BASE_URL
    timeout_seconds: 10
    retries: 3
    retry_backoff_factor: 2
    fallback_status: source_unavailable
  satellite_map:
    connector_name: NominatimConnector
    mode: real
    base_url_env: NOMINATIM_BASE_URL
    timeout_seconds: 15
    retries: 2
    retry_backoff_factor: 2
    fallback_status: source_unavailable
```

### 2.6 HTTP connector client (main app side)

New file: `backend/app/verification_engine/adapters/http_connector_client.py`

- `HTTPConnectorClient(connector_name, base_url, timeout, retries, backoff_factor)`
- `verify(extracted_fields: dict) -> AdapterResult`
- Uses `httpx` for async HTTP calls.
- **Retry with exponential backoff** via `tenacity`: retries on 5xx and network errors; never retries on 4xx.
- **Circuit breaker (D-21):** small **manual** state machine — `closed` / `open` / `half-open` — with configurable failure threshold and cooldown. Use `tenacity` for retry/backoff only; do **not** add the `circuitbreaker` library. After N consecutive failures, open circuit and return `source_unavailable` without attempting the call. Half-open allows a probe after cooldown; success closes, failure re-opens.
- On timeout or open circuit: return `AdapterResult(status=source_unavailable, ...)` — **never crash**.
- On HTTP 503 (outage): return `AdapterResult(status=source_unavailable, reason="service unavailable")`.
- Logs `[SIMULATED]` prefix for all calls when registry mode is `simulated`.

### 2.7 Update adapter registry

`backend/app/verification_engine/adapters/registry.py`:
- Load `connector_registry.yaml` at startup.
- For each document type, instantiate the appropriate `HTTPConnectorClient` (or `NominatimConnector` for real geocoding).
- Remove all hardcoded `_REGISTRY` dict entries.

### Files changed
| File | Change |
|------|--------|
| `simulated_issuers/` (entire dir) | **NEW** — separate FastAPI app |
| `backend/app/verification_engine/configs/connector_registry.yaml` | **NEW** |
| `backend/app/verification_engine/adapters/http_connector_client.py` | **NEW** |
| `backend/app/verification_engine/adapters/registry.py` | Load from YAML; instantiate HTTP clients |
| `backend/app/verification_engine/adapters/external_stubs.py` | Remove direct mock calls; delegate to HTTP client |
| `backend/.env.example` | Add `SIMULATED_ISSUERS_URL`, `SIMULATED_ISSUERS_PORT` (default 8001), plus per-issuer base URLs |
| `simulated_issuers/.env.example` | `SIMULATED_ISSUERS_PORT=8001`; fail loudly if port in use |
| `simulated_issuers/requirements.txt` | `fastapi`, `uvicorn`, `pyyaml`, `httpx` |

### New dependencies (main app)
```
httpx>=0.27         # async HTTP client for connector calls
tenacity>=8.3       # retry + backoff
pyyaml>=6.0         # connector registry YAML loading
```

### Tests
- `tests/test_simulated_issuer_service.py` (runs simulated issuer in-process via `httpx.AsyncClient(app=...)`):
  - **(Addendum test a)** Every status reachable via fixture key lookup — parametrised over all 6 statuses × all 6 connectors.
  - **(Addendum test b)** Simulated "verified" response always has `"official_verification": false` and `"simulated": true`.
  - **(Addendum test c)** `FORCE_OUTAGE=true` → all endpoints return 503 → `AdapterResult.status == source_unavailable` (not a crash).
  - Timeout injection → `source_unavailable` (not a crash).
  - Circuit breaker state transitions (`closed` → `open` → `half-open` → `closed`/`open`); open circuit or timeout → `source_unavailable` (never crash).
  - Busy port at simulated-issuer startup → clear failure (does not bind alternate port).
  - Registry YAML reload: changing `mode: simulated` → `mode: real` with a different base URL wires to a different HTTP client.

---

## Phase 3 — Enhanced Extraction

**Goal:** Add LLM-structured extraction as fallback, QR decode + field comparison, Hindi/Marathi OCR support. (Phase number shifted from original Phase 2.)

### 3.1 LLM extraction module (`app/document_processing/llm_extractor.py`) — D-16 / Q1
- Abstract `LLMExtractor` base class with `extract(text: str, schema: dict) -> dict` (strict JSON schema).
- Provider selected via `.env`: `LLM_PROVIDER=gemini|openai|none`.
  - **`gemini`** (default adapter): `GeminiLLMExtractor` via `google-generativeai`.
  - **`openai`**: `OpenAILLMExtractor`.
  - **`none`**: `NullLLMExtractor` — skip LLM entirely; system runs on OCR + regex parsers only (no API key required).
- LLM is used only for: classification fallback, structured field extraction (strict JSON schema), and explanation text.
- Called in `orchestrator.py` after regex extraction when: (a) required fields are still missing AND (b) `ENABLE_AI_EXTRACTION=true` AND (c) `LLM_PROVIDER != none`.
- Output merged with regex results; LLM fields flagged `source="llm"`.
- **LLM never makes pass/fail decisions** — deterministic code owns all pass/fail.

### 3.2 QR decode + field comparison (`app/document_processing/qr_processor.py`)
- Uses `pyzbar` (optional import; degrades if missing).
- Decodes QR payloads from rendered PDF page images.
- Compares payload fields against already-extracted fields.
- Returns `QRCheckResult` with `match`/`mismatch`/`payload_unreadable`/`qr_absent`.

### 3.3 Hindi/Marathi OCR
- `OCR_LANGUAGES=eng+hin+mar` in `.env.example`.
- Validate `hin`/`mar` tessdata availability in `tesseract_status()`.
- Add Hindi/Marathi field aliases to `field_extractor.py` for all document types.

### 3.4 Extend `FieldCandidate` / extracted fields — D-20 / Q5 (extraction side)
- Add `raw_snippet: Optional[str]` field.
- Store the raw extracted value **exactly as it appears**; add a separate `normalized_value` (transliteration / ASCII normalization). **Never overwrite the original.**

### Files changed
| File | Change |
|------|--------|
| `app/document_processing/llm_extractor.py` | **NEW** — generic interface + Gemini / OpenAI / none |
| `app/document_processing/qr_processor.py` | **NEW** |
| `app/document_processing/field_extractor.py` | Hindi/Marathi aliases; `raw_snippet`; `normalized_value` |
| `app/document_processing/intelligence_types.py` | Add `raw_snippet`, `normalized_value` |
| `app/document_processing/orchestrator.py` | Call LLM extractor; call QR processor |
| `app/document_processing/ocr_processor.py` | Add multi-language validation |
| `.env.example` | Add `OCR_LANGUAGES`, `LLM_PROVIDER=gemini|openai|none`, `LLM_MODEL`, `ENABLE_AI_EXTRACTION` |

### New dependencies
```
pyzbar>=0.1.9
google-generativeai>=0.7   # optional LLM (Gemini, default) — requirements-optional.txt
openai>=1.0                # optional LLM (OpenAI) — requirements-optional.txt
indic-transliteration>=2.3 # normalized_value at extraction time (D-20)
```

### Tests
- `tests/test_qr_processor.py`: synthetic QR with known payload; mismatch case.
- `tests/test_llm_extractor.py`: mock Gemini/OpenAI; `LLM_PROVIDER=none` uses OCR+regex only; no pass/fail from LLM.

---

## Phase 4 — pyHanko PKI Chain + Config Extensions

**Goal:** Real PDF signature chain validation; extend config schema with `arithmetic_checks`, `conditional_checks`, `aph_clause`.

### 4.1 pyHanko adapter (`app/verification_engine/adapters/pdf_signature_pyhanko.py`) — D-17 / Q2
- `verify_pdf_signature_pyhanko(ctx) -> AdapterResult`.
- Trust store path: `TRUST_STORE_DIR` in `.env` (**empty by default**). No CCA India bundle is shipped or invented.
- Returns: `signature_present_valid`, `signature_present_chain_untrusted`, `signature_present_modified_after_signing`, `signature_absent`, `signature_check_failed`, plus chain status `chain_untrusted_no_trust_store` when no trust roots are loaded.
- **If no trust roots and PDF is signed:** verify integrity and modification-after-signing for real; report chain status `chain_untrusted_no_trust_store`; set `external_verification_status` to `manual_review_required` with the limitation stated in the report.
- **Scanned signatures or stamps:** signature check = `not_applicable`.
- Falls back to existing sigflags heuristic if pyHanko not installed.
- Clearly states in output whether pyHanko or sigflags was used.
- CCA India root download procedure is documented only in `docs/INTEGRATION_RESEARCH.md` (operators add certs to `TRUST_STORE_DIR`).

### 4.2 Config schema extension
```json
{
  "layer1": {
    "arithmetic_checks": [
      {
        "id": "BALANCE_SHEET_BALANCE",
        "description": "Assets = Liabilities + Equity",
        "fields_lhs": ["total_assets"],
        "fields_rhs": ["total_liabilities", "total_equity"],
        "tolerance_pct": 1.0,
        "severity": "failed",
        "aph_clause": "TODO: fill from APH §X.Y",
        "source_note": "SYNTHETIC"
      }
    ],
    "conditional_checks": [
      {
        "id": "STRUCTURAL_CERT_AGE",
        "condition_field": "building_age_years",
        "condition_op": "gt",
        "condition_value": "TODO: threshold from APH",
        "then_require": ["structural_stability_certificate"],
        "severity": "failed",
        "aph_clause": "TODO: fill from APH §X.Y"
      }
    ]
  }
}
```

### 4.3 Layer1 evaluator extension (`layer1.py`)
- Add `_evaluate_arithmetic_checks()`.
- Add `_evaluate_conditional_checks()`.

### 4.4 Update all 7 document configs (including Affidavit 2)
- Add `aph_clause: "TODO: fill from APH §X.Y"` to every rule entry.
- Add `source_note` field.
- Add `arithmetic_checks` to `audited_accounts.json`.
- Add `conditional_checks` to `structural_stability.json`.

### Files changed
| File | Change |
|------|--------|
| `app/verification_engine/adapters/pdf_signature_pyhanko.py` | **NEW** — trust-store-aware; `chain_untrusted_no_trust_store` |
| `app/verification_engine/adapters/pdf_signature.py` | Delegate to pyHanko; keep sigflags fallback |
| `app/verification_engine/layer1.py` | Add arithmetic + conditional check evaluators |
| `app/verification_engine/configs/*.json` | Add `aph_clause`, `source_note`, `arithmetic_checks`, `conditional_checks` |
| `app/verification_engine/loader.py` | Validate extended schema on load |
| `.env.example` | Add `TRUST_STORE_DIR=` (empty by default) |
| `docs/INTEGRATION_RESEARCH.md` | CCA India trust-root download instructions (no certs bundled) |

### New dependencies
```
pyhanko>=0.21
pyhanko-certvalidator>=0.24
```

### Tests
- `tests/test_pyhanko_adapter.py`: signed/unsigned/modified-after-signing; empty trust store → `chain_untrusted_no_trust_store` + `manual_review_required`; scanned → `not_applicable`.
- `tests/test_layer1_arithmetic.py`: balance check pass/fail.
- `tests/test_layer1_conditional.py`: structural cert conditional.

---

## Phase 5 — Forensics Triage Score + Enhanced Forensics

**Goal:** Numeric triage score with configurable weights; ELA; pHash; text-layer vs. render mismatch; hidden/overlaid text.

### 5.1 Forensics triage score (`app/document_processing/forensics_score.py`)
```python
@dataclass
class SignalScore:
    signal_code: str
    raw_score: float       # 0–1
    weight: float          # from config
    contribution: float    # raw_score × weight
    reason: str
    confidence: float
    evidence_region: Optional[str]
    interpretation: str    # always "preliminary indicator requiring human verification"

@dataclass
class TriageScore:
    total: float           # 0–100
    signals: list[SignalScore]
    interpretation: str    # always "preliminary indicator requiring human verification"
    config_version: str
```

Default weights config (`app/verification_engine/configs/forensics_weights.json`):
```json
{
  "version": "v1",
  "weights": {
    "metadata_anomaly":         0.05,
    "malformed_structure":      0.20,
    "unusual_modification":     0.10,
    "signature_absent":         0.05,
    "signature_invalid":        0.30,
    "qr_mismatch":              0.25,
    "near_duplicate":           0.15,
    "duplicate_hash":           0.10,
    "ela_anomaly":              0.25,
    "hidden_text":              0.30,
    "incremental_update_abuse": 0.20
  }
}
```

### 5.2 ELA (`app/document_processing/forensics_image.py`)
- Error Level Analysis using Pillow re-save at quality 95 + pixel difference.
- Heuristic threshold from config.

### 5.3 pHash (`forensics_image.py`)
- `phash_hex()` using DCT-based perceptual hash (Pillow/imagehash).
- Hamming distance comparison across application corpus.

### 5.4 PDF hidden/overlaid text detection (`forensics.py` extension)
- Detect text blocks with opacity < 0.01 or colour == page background.
- Detect text-layer vs. rendered-image mismatch using a diff threshold.

### 5.5 Incremental update abuse
- Count `%%EOF` markers; check xref consistency.

### Files changed
| File | Change |
|------|--------|
| `app/document_processing/forensics_score.py` | **NEW** |
| `app/document_processing/forensics_image.py` | **NEW** (ELA, pHash) |
| `app/document_processing/forensics.py` | Add hidden-text, incremental-update, call `forensics_score` |
| `app/verification_engine/configs/forensics_weights.json` | **NEW** |
| `app/services/forensics_service.py` | Include `TriageScore` in run summary |
| `app/schemas/engine.py` | Add `TriageScoreOut` to `ApplicationResultOut` |

### New dependencies
```
opencv-python-headless>=4.9
imagehash>=4.3
```

### Tests
- `tests/test_forensics_score.py`: all-pass vs. all-fail signals; weight override.
- `tests/test_ela.py`: clean vs. re-saved JPEG.
- `tests/test_phash.py`: identical vs. slightly different images.

---

## Phase 6 — Fuzzy Reconciliation + Transliteration

**Goal:** Fuzzy string matching with configurable thresholds; Hindi/Marathi transliteration normalization.

### 6.1 Fuzzy match (`app/document_processing/reconciliation.py` extension)
- `fuzzy_comparable(field_name, value_a, value_b, threshold) -> MatchKind`.
- Uses `rapidfuzz.fuzz.token_sort_ratio`.
- Threshold from `reconciliation_thresholds.json` per field.

### 6.2 Transliteration normalization — D-20 / Q5 (reconciliation side)
- Compare using **`normalized_value`** fields (produced in Phase 3) plus fuzzy matching with config thresholds.
- `indic-transliteration` for Hindi/Marathi → IAST / ASCII when a normalized value is missing.
- Applied to `institution_name`, `trust_name`, `address`.
- Evidence must show **both** the original extracted value and the normalized form — never overwrite originals.

### Files changed
| File | Change |
|------|--------|
| `app/document_processing/reconciliation.py` | Fuzzy compare on normalized values; dual evidence (raw + normalized) |
| `app/verification_engine/configs/reconciliation_thresholds.json` | **NEW** |

### New dependencies
```
rapidfuzz>=3.6
indic-transliteration>=2.3
```

### Tests
- `tests/test_reconciliation.py`: fuzzy cases; evidence includes both original and normalized forms.

---

## Phase 7 — Hash-chained Audit Log

**Goal:** Append-only SHA-256 hash-chained audit log with chain integrity verification.

### 7.1 New table `audit_chain_events`
```python
class AuditChainEvent(Base):
    id: str (uuid)
    sequence: int (autoincrement)
    action: str
    actor_id: str
    actor_role: str
    application_id: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[str]
    rule_version: Optional[str]
    connector_used: Optional[str]
    mode: str                  # REAL | SIMULATED
    input_hash: Optional[str]  # SHA-256 of input doc/fields
    result_summary: str        # non-PII JSON
    created_at: datetime
    prev_hash: str             # SHA-256 of previous row's chain_hash
    chain_hash: str            # SHA-256(prev_hash + this row data)
```

### 7.2 `audit_chain_service.py`
- `record_chain_event(db, **kwargs) -> AuditChainEvent`.
- `verify_chain_integrity(db, from_seq, to_seq) -> IntegrityResult`.

### 7.3 Admin API
- `GET /api/v1/admin/audit-chain/verify` — returns chain integrity status.

### Files changed
| File | Change |
|------|--------|
| `app/models/audit_chain.py` | **NEW** |
| `app/services/audit_chain_service.py` | **NEW** |
| `app/api/routes/admin.py` | Add chain verify endpoint |
| `app/verification_engine/pipeline.py` | Call `record_chain_event` after each run; record `mode` field |
| `alembic/versions/` | New migration |

### Tests
- `tests/test_audit_chain.py`: record 5 events; verify passes; tamper 1 row; verify fails.

---

## Phase 8 — Reports: JSON + PDF

**Goal:** Structured JSON export of `ApplicationResultOut` and a human-readable PDF scrutiny report. Every report must include REAL/SIMULATED labels and must not imply authenticity when no official source confirmed the document.

### 8.1 JSON report (`app/services/report_service.py`)
- `generate_application_report(db, application_id) -> ApplicationResultOut`.
- Assembles `DocumentResultOut` for each document.
- Includes: statuses, findings, forensic signals, triage score, cross-doc findings.
- Mandatory fields per addendum §6:
  - `rule_set_version`, `engine_version`, `generated_at`
  - Per-document: rule findings with evidence and page refs, signature status (or `"not applicable: scanned"`), cross-doc findings, per-check REAL/SIMULATED label, verification statuses, recommended actions.
  - `report_disclaimer`: explicit statement if no official source confirmed any document.
  - `official_source_confirmed: false` on each document where all `verification_results` are SIMULATED.

### 8.2 Report disclaimer logic

```python
def _build_disclaimer(doc_results: list[DocumentResultOut]) -> str:
    unconfirmed = [d for d in doc_results if not d.official_source_confirmed]
    if unconfirmed:
        names = ", ".join(d.requirement_code for d in unconfirmed)
        return (
            f"IMPORTANT: The following documents were NOT confirmed by any official "
            f"external source. Rule-based checks were applied, but these checks do "
            f"not constitute official verification: {names}. "
            f"All simulated results are marked [SIMULATED] and have "
            f"official_verification=false."
        )
    return "All documents were verified against official sources."
```

> **(Addendum test d)** If any `DocumentResultOut.official_source_confirmed == False`, the report JSON and PDF must include a disclaimer that explicitly states no official source confirmed the document. CI test asserts this.

### 8.3 PDF report — D-18 / Q3
- Uses `weasyprint` (HTML → PDF). No specific AICTE format is mandated.
- **Single template** `app/templates/scrutiny_report.html` (restyle later in one place).
- Templated sections:
  - Header
  - Application summary
  - Rule-set version
  - Per-document findings with evidence and page refs
  - Signature status (incl. `not_applicable` for scanned)
  - REAL / SIMULATED labels
  - Cross-document findings
  - Recommended actions
  - Reviewer sign-off block
- Permanent notice on every report: **"Decision-support output; final decision rests with the competent authority."**
- Each finding row shows: rule_id, severity, evidence, page ref, clause ref.
- Each connector result row shows: `[REAL]` or `[SIMULATED]` badge, status, `scope_of_confirmation`, `official_verification`.
- Footer: disclaimer text from 8.2 + the permanent decision-support notice.

### 8.4 API endpoints
- `GET /api/v1/applications/{id}/report.json`
- `GET /api/v1/applications/{id}/report.pdf`

### Files changed
| File | Change |
|------|--------|
| `app/services/report_service.py` | **NEW** |
| `app/templates/scrutiny_report.html` | **NEW** |
| `app/api/routes/applications.py` | Add report endpoints |

### New dependencies
```
weasyprint>=62
jinja2>=3.1
```

### Tests
- `tests/test_report_service.py`:
  - JSON report structure; PDF non-empty byte stream.
  - **(Addendum test d)** Asserts report JSON contains explicit "not confirmed by official source" statement when all connectors are SIMULATED.
  - Asserts no document with `official_source_confirmed=False` uses the word "verified" in a context implying authenticity.

---

## Phase 9 — Synthetic Dataset + Evaluation Harness

**Goal:** Mandatory per spec; enables quantitative DoD validation.

### 9.1 Synthetic dataset generator (`tests/synthetic/generator.py`)

**Defect catalogue:**
| Code | Description |
|------|-------------|
| `CLEAN` | No defect |
| `EXPIRED_CERT` | Expiry date in the past |
| `EDITED_EXPIRY` | Date field value inconsistent with PDF metadata |
| `NAME_MISMATCH` | Institution name differs across 2 documents |
| `WRONG_SURVEY_NO` | Survey number differs from application |
| `AREA_BELOW_NORM` | Land area below configured minimum |
| `MISSING_MANDATORY_DOC` | Required doc type absent |
| `DUPLICATE_PDF` | Same bytes submitted twice |
| `REUSED_PHOTO` | Same image embedded in two different documents |
| `TAMPERED_SCAN` | JPEG quality inconsistency via ELA injection |
| `INVALID_QR` | QR code payload mismatches body text |
| `UNSIGNED_PDF` | No digital signature where expected |
| `MODIFIED_AFTER_SIGNING` | Incremental update after signature |
| `WRONG_FY` | Financial year field conflicts with document date |
| `UNBALANCED_ACCOUNTS` | Total assets ≠ total liabilities + equity |
| `MISSING_ENTRANCE_MARKER` | Satellite map lat/lon absent |
| `COORD_MISMATCH` | Coordinates point to wrong location |
| `SIMULATED_ALL_STATUSES` | Six variants with different fixture keys to trigger each of the 6 external statuses |

### 9.2 Evaluation harness (`tests/synthetic/evaluate.py`)
- Runs the full pipeline on each synthetic file.
- Compares actual findings against `ground_truth.json`.
- Outputs: per-field extraction accuracy, per-defect precision/recall/F1, confusion matrix, false-positive rate, average processing time.

### Files changed
| File | Change |
|------|--------|
| `tests/synthetic/__init__.py` | **NEW** |
| `tests/synthetic/generator.py` | **NEW** |
| `tests/synthetic/ground_truth.json` | **NEW** (generated, committed) |
| `tests/synthetic/evaluate.py` | **NEW** |
| `tests/test_synthetic_evaluation.py` | **NEW** (runs evaluate.py in CI) |

### New dependencies
```
faker>=25.0
reportlab>=4.2
```

---

## Phase 10 — Final Integration + DoD Check

**Goal:** End-to-end clean run on synthetic dataset; all tests pass; README updated.

### 10.1 Integration test
- `tests/test_full_application_integration.py`:
  - Creates a full synthetic application with all 7 doc types (including Affidavit 2).
  - Runs extraction → reconciliation → forensics → three-layer verification → report.
  - Asserts: all three statuses populated; no status is `pending` at end; report JSON valid; audit chain intact.
  - Asserts: no document where only rule checks ran shows `external_verification_status == "verified"`.

### 10.2 README update
- "Engine architecture" section.
- "Running tests and evaluation" section with real command output.
- "Adding a new document type" section.
- "Running the simulated issuer service" section.

### 10.3 `DECISIONS.md`
- Formalise all D-01 through D-21 decisions (including Q1–Q7 locks).

---

## Dependency Summary (new additions across all phases)

```
# requirements.txt additions (main app)
httpx>=0.27
tenacity>=8.3
pyyaml>=6.0
pyhanko>=0.21
pyhanko-certvalidator>=0.24
pyzbar>=0.1.9
opencv-python-headless>=4.9
imagehash>=4.3
rapidfuzz>=3.6
indic-transliteration>=2.3
weasyprint>=62
jinja2>=3.1

# requirements-optional.txt (new file — LLM; system degrades without them)
google-generativeai>=0.7
openai>=1.0

# requirements-dev.txt (new file)
faker>=25.0
reportlab>=4.2   # synthetic PDF generation only; scrutiny reports use WeasyPrint
pytest-cov>=5.0
pytest-timeout>=2.3

# simulated_issuers/requirements.txt (separate service)
fastapi>=0.111
uvicorn>=0.30
pyyaml>=6.0
httpx>=0.27
```

---

## Test Plan (summary)

| Phase | New test files | Key assertions |
|-------|---------------|----------------|
| 0 | `test_inspector_classifier.py` (extended) | New semantic categories |
| 0b | `test_inspector_classifier.py`, `test_layer1_affidavit2.py` | Affidavit 2 classifies; required-field rules work |
| 1 | `test_engine_models.py` | Pydantic validation; SIMULATED+official_verification=True raises error **(test b)** |
| 2 | `test_simulated_issuer_service.py` | All 6 statuses reachable **(test a)**; SIMULATED verified has `official_verification=false` **(test b)**; outage → `source_unavailable` **(test c)**; circuit breaker state machine; busy port fails loudly |
| 3 | `test_qr_processor.py`, `test_llm_extractor.py` | QR match/mismatch; Gemini/OpenAI/`none` modes; raw + `normalized_value` |
| 4 | `test_pyhanko_adapter.py`, `test_layer1_arithmetic.py`, `test_layer1_conditional.py` | Empty trust store → `chain_untrusted_no_trust_store`; scanned → `not_applicable`; arithmetic; conditional |
| 5 | `test_forensics_score.py`, `test_ela.py`, `test_phash.py` | Score computation; ELA; pHash |
| 6 | `test_reconciliation.py` (extended) | Fuzzy + transliteration; evidence shows original and normalized |
| 7 | `test_audit_chain.py` | Chain integrity; tamper detection |
| 8 | `test_report_service.py` | JSON structure; decision-support notice; no "verified" implied when SIMULATED **(test d)** |
| 9 | `test_synthetic_evaluation.py` | F1 ≥ 0.80 on synthetic defects |
| 10 | `test_full_application_integration.py` | End-to-end on full application; DoD check |

---

## Resolved Decisions (Q1–Q7)

> Locked 2026-10-27. Mapped to ADR **D-16 … D-21**. Phase implementation may proceed sequentially.

| Q | Topic | Decision |
|---|--------|----------|
| **Q1** | LLM provider | Generic interface; `LLM_PROVIDER=gemini\|openai\|none`. Gemini = default adapter; OpenAI = second; `none` = OCR + regex only (no API key). LLM for classification fallback, structured JSON extraction, explanation text only — **never pass/fail**. → **D-16** |
| **Q2** | pyHanko trust store | No CCA India bundle. `TRUST_STORE_DIR` configurable (empty default). Signed + no roots → integrity/mod-after-sign for real; chain `chain_untrusted_no_trust_store`; `external_verification_status=manual_review_required` + report limitation. CCA roots from official CCA source only — document in `INTEGRATION_RESEARCH.md`; never bundle/invent certs. Scanned signatures/stamps → `not_applicable`. → **D-17** |
| **Q3** | PDF report | No mandated AICTE format. Clean professional HTML → PDF; single template with listed sections + permanent *"Decision-support output; final decision rests with the competent authority"* notice. → **D-18** |
| **Q4** | Phase ordering | **Sequential.** Review/test each phase before the next. Parallelize **tests only**, not implementation. → **D-19** |
| **Q5** | Transliteration | **Both** layers: extraction keeps raw + `normalized_value`; reconciliation compares normalized + fuzzy (config thresholds); evidence shows both forms. → **D-20** |
| **Q6** | Simulated issuer port | **8001** default; `SIMULATED_ISSUERS_URL` / `SIMULATED_ISSUERS_PORT` in `.env`. Busy port → clear startup error (no silent switch). → **D-11** |
| **Q7** | Circuit breaker | `tenacity` retry/backoff + **manual** closed/open/half-open state machine (configurable threshold/cooldown). No `circuitbreaker` library. Unit-test transitions; open/timeout → `source_unavailable`, never crash. → **D-21** |

---

*Decisions locked. Implement phase-by-phase for review (D-19).*
