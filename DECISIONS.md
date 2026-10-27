# PRAMAN Architecture Decisions (D-01 … D-21)

Locked from `PLAN.md` (2026-10-27).

| ID | Decision |
|----|----------|
| D-01 | Keep `verification_engine/pipeline.py` as three-layer orchestrator; extend, not replace. |
| D-02 | Extend existing JSON configs with `aph_clause`, `source_note`, arithmetic/conditional checks. |
| D-03 | Fixture mocks live in HTTP `simulated_issuers/` (supersedes direct mock imports). |
| D-04 | Optional `pyHanko` for PDF signatures; sigflags fallback. |
| D-05 | Optional `pyzbar` / OpenCV for QR and image forensics. |
| D-06 | `rapidfuzz` (+ transliteration) for reconciliation. |
| D-07 | WeasyPrint HTML→PDF for scrutiny reports (single Jinja template). |
| D-08 | Hash-chained `audit_chain_events` separate from `AuditEvents`. |
| D-09 | Engine DTOs in `app/schemas/engine.py` (not ORM). |
| D-10 | Synthetic generator under `tests/synthetic/`. |
| D-11 | Simulated issuers on configurable port 8001; busy port fails loudly. |
| D-12 | Connector registry YAML maps document adapters / modes / URLs. |
| D-13 | `official_verification` forced false when `mode=SIMULATED`. |
| D-14 | Affidavit 2 config with APH TODO placeholders. |
| D-15 | Real APIs research-only in `docs/INTEGRATION_RESEARCH.md`; no scraping. |
| D-16 | LLM: `gemini\|openai\|none`; never pass/fail. |
| D-17 | `TRUST_STORE_DIR` empty by default; no CCA certs bundled. |
| D-18 | Professional HTML→PDF report + decision-support notice. |
| D-19 | Sequential phase implementation; parallelize tests only. |
| D-20 | Raw + `normalized_value` in extraction; compare normalized in reconciliation. |
| D-21 | `tenacity` + manual circuit breaker; no `circuitbreaker` library. |
