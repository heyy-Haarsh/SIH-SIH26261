"""Generate synthetic document texts + ground-truth defect labels."""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "out"


def generate() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = [
        {
            "id": "SYN-FIRE-MISSING",
            "requirement_code": "FIRE_NOC",
            "text": "Issuing Authority: Fire Dept\nIssue Date: 2024-01-01\n",
            "defects": ["missing_certificate_number"],
        },
        {
            "id": "SYN-FIRE-OK",
            "requirement_code": "FIRE_NOC",
            "text": (
                "Certificate Number: FIRE-VERIFIED-001\n"
                "Issuing Authority: Fire Dept\n"
                "Issue Date: 2024-01-01\n"
                "Valid Until: 2028-01-01\n"
                "Institution Name: Demo Institute\n"
            ),
            "defects": [],
        },
        {
            "id": "SYN-PAY-MISSING-TXN",
            "requirement_code": "AICTE_PAYMENT_RECEIPT",
            "text": "Receipt Number: R1\nPayment Amount: 1000\nPayment Date: 2024-06-01\n",
            "defects": ["missing_transaction_id"],
        },
        {
            "id": "SYN-ACCT-BALANCE-FAIL",
            "requirement_code": "AUDITED_ACCOUNTS",
            "text": (
                "Financial Year: 2024-25\nAuditor Name: A CA\nIssue Date: 2025-01-10\n"
                "Total Assets: 100\nTotal Liabilities: 10\nTotal Equity: 10\n"
            ),
            "defects": ["arithmetic_mismatch"],
        },
        {
            "id": "SYN-NAME-FUZZY",
            "requirement_code": "AFFIDAVIT",
            "text": "Institution Name: Demo Institute of Technology\n",
            "defects": [],
            "pair_text": "Institution Name: Demo Inst. of Technology\n",
        },
    ]
    ground = {"version": "v1", "samples": samples}
    path = OUT_DIR / "ground_truth.json"
    path.write_text(json.dumps(ground, indent=2), encoding="utf-8")
    for s in samples:
        (OUT_DIR / f"{s['id']}.txt").write_text(s["text"], encoding="utf-8")
    return path


if __name__ == "__main__":
    p = generate()
    print(f"Wrote {p}")
