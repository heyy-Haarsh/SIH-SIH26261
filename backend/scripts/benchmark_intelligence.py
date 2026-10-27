"""Reproducible probe of the document-intelligence checks that exist today.

This is not a measured accuracy benchmark. There is no labelled corpus of real AICTE
documents in this repository, so the script only runs the synthetic cases below and
prints latency. Do not quote its counts as classification or OCR accuracy.

Usage (from the backend directory):
    .\\.venv\\Scripts\\python.exe scripts\\benchmark_intelligence.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from app.document_processing.clarity import _assess_image
from app.document_processing.intelligence_types import PageText
from app.document_processing.ocr_processor import tesseract_status
from app.document_processing.semantic_classifier import SemanticDocumentClassifier
from app.models.enums import SemanticDocumentCategory

CASES = [
    ("affidavit.txt body", "scan.pdf", "This affidavit is solemnly sworn by the deponent.", SemanticDocumentCategory.AFFIDAVIT),
    ("filename only", "fire_noc.pdf", "See attached.", SemanticDocumentCategory.FIRE_NOC),
    ("no signal", "doc.pdf", "hello there", SemanticDocumentCategory.UNKNOWN),
    ("marathi affidavit", "doc.pdf", "प्रतिज्ञापत्र शपथ पत्र", SemanticDocumentCategory.AFFIDAVIT),
]


def main() -> None:
    clf = SemanticDocumentClassifier()
    rows = []
    latencies = []
    for name, file_name, text, expected in CASES:
        page = PageText(page_number=1, text=text, source="pdf_text", char_count=len(text))
        start = time.perf_counter()
        result = clf.classify(file_name=file_name, pages=[page])
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        rows.append(
            {
                "case": name,
                "expected": expected.value,
                "predicted": result.category.value,
                "matched_expectation": result.category == expected,
                "confidence": result.confidence,
                "method": result.method,
                "latency_ms": round(elapsed, 3),
            }
        )

    blank = _assess_image(Image.new("RGB", (400, 400), (240, 240, 240)))
    report = {
        "kind": "synthetic_probe",
        "labelled_document_count": 0,
        "note": (
            "No labelled evaluation set is checked in. These rows only show that the "
            "heuristic behaves as coded. They are not an accuracy score."
        ),
        "ocr": {
            "available": tesseract_status().get("available"),
            "languages_usable": tesseract_status().get("languages_usable"),
            "message": tesseract_status().get("message"),
        },
        "classification_cases": rows,
        "clarity_blank_image": blank,
        "latency_ms": {
            "median": round(statistics.median(latencies), 3),
            "max": round(max(latencies), 3),
            "n": len(latencies),
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
