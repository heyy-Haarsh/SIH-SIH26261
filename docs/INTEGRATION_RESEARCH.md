# Integration Research — Real External Sources

**Status:** research only. No real connectors are implemented unless an API is public, documented, authorized, and credentials are available.

**Hard rules:** no scraping, no CAPTCHA bypass, no terms-of-use violation. If registration/credentials are missing, adapters return `source_unavailable` with reason:

> `API access requires institutional registration; credentials not provided`

---

## CCA India PKI trust roots (PDF digital signatures)

| Item | Notes |
|------|--------|
| Purpose | Trust anchors for pyHanko chain validation of digitally signed PDFs |
| Official source | Download root certificates only from the **official CCA India** website / published trust list |
| Config | Set `TRUST_STORE_DIR` in `.env` to a local folder containing those PEM/CRT files |
| Bundled in repo? | **No.** Do not invent, embed, or commit certificates |
| Behaviour if empty | Integrity + modification-after-signing still checked; chain status `chain_untrusted_no_trust_store`; `external_verification_status=manual_review_required` with limitation in the report |
| Scanned stamps/signatures | Signature check = `not_applicable` |

---

## DigiLocker

| Item | Notes |
|------|--------|
| What is publicly documented | DigiLocker offers APIs for issued documents via partner/issuer integration; national digital locker for citizens |
| Registration / access | Requires DigiLocker partner / issuer onboarding and credentials |
| Feasibility (student team) | Low without institutional partnership |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## API Setu

| Item | Notes |
|------|--------|
| What is publicly documented | Government API gateway aggregating department APIs; catalogue and access via API Setu portal |
| Registration / access | Requires registration, API keys, and often department-level approval |
| Feasibility (student team) | Low–medium for demo; production needs authorization |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## AICTE payment portal

| Item | Notes |
|------|--------|
| What is publicly documented | Payment / portal UX for institutions; no public, documented receipt-verification API identified for third-party scrutiny tools |
| Registration / access | Institutional AICTE login; no authorized third-party verify API for this project |
| Feasibility (student team) | Use **simulated issuer** only |
| Stub reason | `No public documented payment verification API; credentials not provided` |
| Real adapter now? | **No** — simulated issuer only |

---

## Fire safety authority

| Item | Notes |
|------|--------|
| What is publicly documented | State/municipal fire NOC processes vary by jurisdiction; no single national public verify API |
| Registration / access | Typically departmental; not available to this team |
| Feasibility (student team) | Simulated issuer only |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## Building / occupancy authority

| Item | Notes |
|------|--------|
| What is publicly documented | Local development authorities issue occupancy/completion certificates; APIs rarely public |
| Registration / access | Authority-specific; not provided |
| Feasibility (student team) | Simulated issuer only |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## Structural engineer registry (NSET / state council)

| Item | Notes |
|------|--------|
| What is publicly documented | Some states publish engineer membership lists; NSET / councils vary; no uniform national verify API confirmed for this use case |
| Registration / access | Registry-specific; often website-only / login |
| Feasibility (student team) | Simulated issuer only; no scraping |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## ICAI membership portal

| Item | Notes |
|------|--------|
| What is publicly documented | ICAI provides member search / membership services for CAs; terms and automation rules must be respected |
| Registration / access | Public search may exist for humans; automated third-party API access is not assumed authorized |
| Feasibility (student team) | Do not scrape; use simulated issuer unless a documented authorized API + credentials are provided |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |

---

## Nominatim / OpenStreetMap (geocoding)

| Item | Notes |
|------|--------|
| What is publicly documented | Public Nominatim usage policy; rate limits; attribution required |
| Registration / access | Public endpoint with usage policy; optional self-hosted |
| Feasibility (student team) | **Opt-in only** via env (`ENABLE_GEOCODE` / related flags); respect rate limits |
| Stub reason | When disabled: `Geocoding disabled or unavailable` |
| Real adapter now? | Existing opt-in stub/adapter path only — not a document authenticity claim |

---

## Affidavit e-stamp connector

| Item | Notes |
|------|--------|
| What is publicly documented | State e-stamp / SHCIL-style systems; verification portals vary; no universal public API for this project |
| Registration / access | Not provided |
| Feasibility (student team) | Simulated issuer (`affidavit_estamp`) only |
| Stub reason | `API access requires institutional registration; credentials not provided` |
| Real adapter now? | **No** |
