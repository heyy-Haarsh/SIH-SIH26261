from app.verification_engine.layer1 import evaluate_layer1


def test_balance_sheet_pass():
    cfg = {
        "is_synthetic_rules": True,
        "layer1": {
            "required_fields": [],
            "arithmetic_checks": [
                {
                    "id": "BALANCE_SHEET_BALANCE",
                    "fields_lhs": ["total_assets"],
                    "fields_rhs": ["total_liabilities", "total_equity"],
                    "tolerance_pct": 1.0,
                    "severity": "failed",
                }
            ],
        },
    }
    result = evaluate_layer1(
        cfg,
        {"total_assets": "100", "total_liabilities": "60", "total_equity": "40"},
    )
    assert result.status == "pass"
    assert any(c.check_code.endswith("_PASS") for c in result.checks)


def test_balance_sheet_fail():
    cfg = {
        "is_synthetic_rules": True,
        "layer1": {
            "required_fields": [],
            "arithmetic_checks": [
                {
                    "id": "BALANCE_SHEET_BALANCE",
                    "fields_lhs": ["total_assets"],
                    "fields_rhs": ["total_liabilities", "total_equity"],
                    "tolerance_pct": 1.0,
                    "severity": "failed",
                }
            ],
        },
    }
    result = evaluate_layer1(
        cfg,
        {"total_assets": "100", "total_liabilities": "10", "total_equity": "10"},
    )
    assert result.status == "fail"
