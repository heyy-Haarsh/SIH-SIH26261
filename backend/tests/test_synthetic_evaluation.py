from tests.synthetic.evaluate import evaluate


def test_synthetic_f1_threshold():
    metrics = evaluate()
    # Synthetic harness smoke: expect non-trivial recall on planted defects
    assert metrics["f1"] >= 0.5
    assert metrics["tp"] + metrics["fn"] >= 1
