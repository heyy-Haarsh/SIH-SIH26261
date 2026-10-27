from app.verification_engine.layer1 import evaluate_layer1


def test_structural_conditional_missing_required():
    cfg = {
        "is_synthetic_rules": True,
        "layer1": {
            "required_fields": [],
            "conditional_checks": [
                {
                    "id": "STRUCTURAL_CERT_AGE",
                    "condition_field": "building_age_years",
                    "condition_op": "gt",
                    "condition_value": "30",
                    "then_require": ["structural_stability_certificate"],
                    "severity": "failed",
                }
            ],
        },
    }
    result = evaluate_layer1(cfg, {"building_age_years": "40"})
    assert result.status == "fail"
    assert any("REQUIRE_MISSING" in c.check_code for c in result.checks)


def test_structural_conditional_ok_when_present():
    cfg = {
        "is_synthetic_rules": True,
        "layer1": {
            "required_fields": [],
            "conditional_checks": [
                {
                    "id": "STRUCTURAL_CERT_AGE",
                    "condition_field": "building_age_years",
                    "condition_op": "gt",
                    "condition_value": "30",
                    "then_require": ["structural_stability_certificate"],
                    "severity": "failed",
                }
            ],
        },
    }
    result = evaluate_layer1(
        cfg,
        {"building_age_years": "40", "structural_stability_certificate": "SSC-1"},
    )
    assert result.status == "pass"
