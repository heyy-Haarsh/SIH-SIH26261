"""Generate PRAMAN demo documents (TXT + simple PDF) for SIH testing.

Output: data/demo_pack/
Upload each file against the requirement_code in MANIFEST.json.
Keys like FIRE-VERIFIED-001 match simulated_issuers fixtures when
USE_SIMULATED_HTTP_ISSUERS=true and simulated_issuers is running.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo_pack"


DOCS: list[dict] = [
    # ---- FIRE_NOC ----
    {
        "file": "01_FIRE_NOC_pass.txt",
        "requirement_code": "FIRE_NOC",
        "expect": "Layer1 pass (synthetic). Layer2: SOURCE_UNAVAILABLE without issuers; SIMULATED verified if HTTP issuers on + FIRE-VERIFIED-001.",
        "text": """Fire Safety Certificate / NOC

Certificate Number: FIRE-VERIFIED-001
Issuing Authority: Municipal Fire Department
Issue Date: 2024-03-15
Valid Until: 2028-03-15
Institution Name: Demo Institute of Technology
Address: 12 Education Road, Pune
""",
    },
    {
        "file": "02_FIRE_NOC_expired.txt",
        "requirement_code": "FIRE_NOC",
        "expect": "Layer1 fail on expired Valid Until. Layer2 may also show expired if issuers on (FIRE-EXPIRED-001).",
        "text": """Fire Safety Certificate / NOC

Certificate Number: FIRE-EXPIRED-001
Issuing Authority: Municipal Fire Department
Issue Date: 2018-01-10
Valid Until: 2020-06-30
Institution Name: Demo Institute of Technology
""",
    },
    {
        "file": "03_FIRE_NOC_missing_fields.txt",
        "requirement_code": "FIRE_NOC",
        "expect": "Layer1 fail — missing certificate_number / dates.",
        "text": """Fire Safety Certificate

Issuing Authority: Fire Dept
Institution Name: Demo Institute of Technology
""",
    },
    # ---- AICTE_PAYMENT_RECEIPT ----
    {
        "file": "04_PAYMENT_pass.txt",
        "requirement_code": "AICTE_PAYMENT_RECEIPT",
        "expect": "Layer1 pass. Layer2 simulated verified with TXN-VERIFIED-001 if issuers on.",
        "text": """AICTE Payment Receipt

Receipt Number: RCP-2025-4412
Payment Amount: 150000.00
Payment Date: 2025-06-12
Transaction ID: TXN-VERIFIED-001
Payment Mode: NEFT
Institution Name: Demo Institute of Technology
UTR Number: TXN-VERIFIED-001
""",
    },
    {
        "file": "05_PAYMENT_missing_txn.txt",
        "requirement_code": "AICTE_PAYMENT_RECEIPT",
        "expect": "Layer1 fail — missing transaction_id.",
        "text": """AICTE Payment Receipt

Receipt Number: RCP-BAD-1
Payment Amount: 1000
Payment Date: 2024-06-01
Institution Name: Demo Institute of Technology
""",
    },
    # ---- OCCUPANCY / BUILDING ----
    {
        "file": "06_OCCUPANCY_pass.txt",
        "requirement_code": "OCCUPANCY_CERTIFICATE",
        "expect": "Layer1 pass. Layer2 simulated with BLD-VERIFIED-001 if issuers on.",
        "text": """Occupancy / Completion Certificate

Certificate Number: BLD-VERIFIED-001
Issue Date: 2023-08-01
Issuing Authority: Municipal Corporation
Address: 12 Education Road, Pune
Valid Until: 2030-01-01
Institution Name: Demo Institute of Technology
Plot Number: P-42
""",
    },
    # ---- STRUCTURAL ----
    {
        "file": "07_STRUCTURAL_pass.txt",
        "requirement_code": "STRUCTURAL_STABILITY",
        "expect": "Layer1 pass. Layer2 engineer credential simulated with ENG-VERIFIED-001 if issuers on.",
        "text": """Structural Stability Certificate

Certificate Number: SSC-2024-778
Issue Date: 2024-02-20
Issuing Authority: Licensed Structural Engineer
Engineer Name: R. Kulkarni
Engineer Registration Number: ENG-VERIFIED-001
Valid Until: 2029-02-20
Institution Name: Demo Institute of Technology
""",
    },
    # ---- AUDITED ACCOUNTS ----
    {
        "file": "08_AUDITED_balance_ok.txt",
        "requirement_code": "AUDITED_ACCOUNTS",
        "expect": "Layer1 pass including arithmetic Assets = Liabilities + Equity.",
        "text": """Audited Statement of Accounts

Financial Year: 2024-25
Auditor Name: S. Mehta
Chartered Accountant: S. Mehta
CA Membership Number: ICAI-VERIFIED-001
Auditor Registration Number: ICAI-VERIFIED-001
Issue Date: 2025-05-01
Institution Name: Demo Institute of Technology
Total Assets: 1000
Total Liabilities: 400
Total Equity: 600
""",
    },
    {
        "file": "09_AUDITED_balance_fail.txt",
        "requirement_code": "AUDITED_ACCOUNTS",
        "expect": "Layer1 arithmetic fail (100 != 10+10).",
        "text": """Audited Statement of Accounts

Financial Year: 2024-25
Auditor Name: A CA
Issue Date: 2025-01-10
Institution Name: Demo Institute of Technology
Total Assets: 100
Total Liabilities: 10
Total Equity: 10
""",
    },
    # ---- SATELLITE MAP ----
    {
        "file": "10_SATELLITE_coords.txt",
        "requirement_code": "SATELLITE_MAP",
        "expect": "Layer1 presence checks. Geocode only if ENABLE_NOMINATIM_GEOCODE=true.",
        "text": """Campus Satellite Map / Geotag

Institution Name: Demo Institute of Technology
Address: 12 Education Road, Pune, Maharashtra
Latitude: 18.5204
Longitude: 73.8567
""",
    },
    # ---- AFFIDAVIT_2 ----
    {
        "file": "11_AFFIDAVIT_2_pass.txt",
        "requirement_code": "AFFIDAVIT_2",
        "expect": "Layer1 pass. Layer2 estamp simulated with ESTAMP-VERIFIED-001 if issuers on.",
        "text": """Affidavit 2

Institution Name: Demo Institute of Technology
Signatory Name: A. Officer
Signatory Designation: Principal
Execution Date: 2026-01-15
Execution Place: Pune
Stamp Paper Ref: ESTAMP-VERIFIED-001
Notary Details: Notary Public, Pune Reg. N-123
E-Stamp Number: ESTAMP-VERIFIED-001
""",
    },
    # ---- Cross-doc name mismatch pair ----
    {
        "file": "12_AFFIDAVIT_name_A.txt",
        "requirement_code": "AFFIDAVIT",
        "expect": "Upload with 13 on same application → reconciliation fuzzy/mismatch demo.",
        "text": """Affidavit

Institution Name: Demo Institute of Technology
Issue Date: 2024-01-10
Document Type: Affidavit
Trust Name: Demo Education Trust
""",
    },
    {
        "file": "13_LAND_name_B_fuzzy.txt",
        "requirement_code": "LAND_OWNERSHIP",
        "expect": "Pair with 12 — names similar for fuzzy match / review.",
        "text": """Registered Lease Deed

Institution Name: Demo Inst. of Technology
Trust Name: Demo Education Trust
Survey Number: 45/2
Land Area: 2.5 acres
Issue Date: 2022-05-01
Address: 12 Education Road, Pune
""",
    },
    {
        "file": "14_LAND_name_mismatch.txt",
        "requirement_code": "LAND_OWNERSHIP",
        "expect": "Clear name mismatch vs Demo Institute of Technology.",
        "text": """Registered Lease Deed

Institution Name: Completely Different College
Trust Name: Other Trust
Survey Number: 99/1
Land Area: 1 acre
Issue Date: 2021-01-01
""",
    },
]


def write_pdf(path: Path, text: str) -> None:
    try:
        import pymupdf
    except ImportError:
        return
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), text, fontsize=11, fontname="helv")
    doc.save(path)
    doc.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in DOCS:
        txt_path = OUT / item["file"]
        txt_path.write_text(item["text"].strip() + "\n", encoding="utf-8")
        pdf_name = item["file"].replace(".txt", ".pdf")
        pdf_path = OUT / pdf_name
        write_pdf(pdf_path, item["text"].strip())
        manifest.append(
            {
                "file_txt": item["file"],
                "file_pdf": pdf_name if pdf_path.exists() else None,
                "requirement_code": item["requirement_code"],
                "expect": item["expect"],
            }
        )
        print(f"Wrote {txt_path.name}" + (f" + {pdf_name}" if pdf_path.exists() else ""))

    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest: {OUT / 'MANIFEST.json'}")
    print(f"Total documents: {len(manifest)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
