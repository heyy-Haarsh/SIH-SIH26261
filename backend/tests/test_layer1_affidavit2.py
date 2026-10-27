"""Phase 0b: Affidavit 2 Layer 1 config checks."""

from datetime import date, timedelta

from app.verification_engine.layer1 import evaluate_layer1
from app.verification_engine.loader import clear_config_cache, get_config_for_requirement


def _cfg():
    clear_config_cache()
    cfg = get_config_for_requirement("AFFIDAVIT_2")
    assert cfg is not None
    return cfg


def test_affidavit2_config_loads():
    cfg = _cfg()
    assert cfg["requirement_code"] == "AFFIDAVIT_2"
    assert cfg.get("is_synthetic_rules") is True
    assert cfg.get("source_note") == "SYNTHETIC"


def test_affidavit2_missing_required_fields_fail():
    result = evaluate_layer1(_cfg(), {}, today=date(2026, 10, 27))
    assert result.status == "fail"
    missing = {c.check_code for c in result.checks if c.outcome in ("fail", "warning")}
    assert "MISSING_INSTITUTION_NAME" in missing
    assert "MISSING_SIGNATORY_NAME" in missing
    assert "MISSING_STAMP_PAPER_REF" in missing


def test_affidavit2_execution_date_not_future():
    fields = {
        "institution_name": "Demo Institute",
        "signatory_name": "A. Officer",
        "signatory_designation": "Principal",
        "execution_date": (date(2026, 10, 27) + timedelta(days=30)).isoformat(),
        "execution_place": "Pune",
        "stamp_paper_ref": "MH-ESTAMP-001",
        "notary_details": "Notary Public, Pune",
    }
    result = evaluate_layer1(_cfg(), fields, today=date(2026, 10, 27))
    assert result.status == "fail"
    assert any(c.check_code == "DATE_FUTURE_EXECUTION_DATE" for c in result.checks)


def test_affidavit2_complete_fields_pass_rules():
    fields = {
        "institution_name": "Demo Institute",
        "signatory_name": "A. Officer",
        "signatory_designation": "Principal",
        "execution_date": "2026-01-15",
        "execution_place": "Pune",
        "stamp_paper_ref": "MH-ESTAMP-001",
        "notary_details": "Notary Public, Pune",
    }
    result = evaluate_layer1(_cfg(), fields, today=date(2026, 10, 27))
    assert result.status == "pass"
    assert not any(c.outcome == "fail" for c in result.checks)


def test_affidavit2_stamp_format_warning_severity_optional():
    """Placeholder format pattern accepts values; missing optional format does not fail alone."""
    fields = {
        "institution_name": "Demo Institute",
        "signatory_name": "A. Officer",
        "signatory_designation": "Principal",
        "execution_date": "2026-01-15",
        "execution_place": "Pune",
        "stamp_paper_ref": "ANY-REF-123",
        "notary_details": "Notary",
    }
    result = evaluate_layer1(_cfg(), fields, today=date(2026, 10, 27))
    assert result.status == "pass"
