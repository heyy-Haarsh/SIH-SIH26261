from app.document_processing.forensics_score import compute_triage_score


def test_all_zero_signals():
    score = compute_triage_score({})
    assert score.total == 0.0
    assert "preliminary" in score.interpretation


def test_weighted_signals():
    score = compute_triage_score({"ela_anomaly": 1.0, "hidden_text": 1.0})
    assert score.total > 0
    assert all("preliminary" in s.interpretation for s in score.signals)


def test_weight_override():
    score = compute_triage_score({"ela_anomaly": 1.0}, weights_override={"ela_anomaly": 1.0})
    assert score.total > 0
