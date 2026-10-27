"""Evaluate Layer-1 defect detection against synthetic ground truth."""

from __future__ import annotations

import json
from pathlib import Path

from app.document_processing.field_extractor import FieldExtractor
from app.document_processing.intelligence_types import PageText
from app.verification_engine.layer1 import evaluate_layer1
from app.verification_engine.loader import clear_config_cache, get_config_for_requirement
from tests.synthetic.generator import generate

OUT_DIR = Path(__file__).resolve().parent / "out"


def evaluate() -> dict:
    gt_path = generate()
    ground = json.loads(gt_path.read_text(encoding="utf-8"))
    clear_config_cache()
    extractor = FieldExtractor()
    tp = fp = fn = 0
    details = []
    for sample in ground["samples"]:
        pages = [PageText(1, sample["text"], "pdf_text", len(sample["text"]))]
        fields_list = extractor.extract_from_pages(pages)
        fields = {f.field_name: f.raw_value for f in fields_list}
        cfg = get_config_for_requirement(sample["requirement_code"])
        predicted: set[str] = set()
        if cfg:
            result = evaluate_layer1(cfg, fields)
            if any(c.check_code.startswith("MISSING_") for c in result.checks if c.outcome == "fail"):
                for c in result.checks:
                    if c.check_code.startswith("MISSING_") and c.outcome == "fail":
                        predicted.add("missing_" + c.check_code.replace("MISSING_", "").lower())
            if any("ARITHMETIC" in c.check_code or c.check_code.endswith("_FAIL") for c in result.checks if c.outcome == "fail"):
                if any("BALANCE" in c.check_code for c in result.checks):
                    predicted.add("arithmetic_mismatch")
        expected = set(sample.get("defects") or [])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        details.append({"id": sample["id"], "expected": sorted(expected), "predicted": sorted(predicted)})
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "details": details}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
