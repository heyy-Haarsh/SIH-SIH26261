PRAMAN DEMO DOCUMENT PACK
=========================
All files are SYNTHETIC, marked DEMO / NOT OFFICIAL, and have no legal validity.
Do not use them for real submissions or as evidence of compliance. Test outcomes are intentions, not guaranteed behavior.

FILES AND TEST INTENT
01_affidavit_complete.pdf — native-text extraction, document matching.
02_fire_safety_complete.pdf — populated fields; external authority should remain unavailable/simulated unless genuinely connected.
03_occupancy_expired.pdf — expired-date rule test; only triggers if a configured rule exists.
04_payment_receipt_mismatch.pdf — cross-document ID mismatch; pair with a test application ID other than APP-DEMO-1001.
05_structural_missing_field.pdf — missing registration-number test.
06_audited_accounts.pdf — financial year and numeric-field extraction.
07_building_plan_metadata.pdf — metadata-only; not an actual plan drawing.
08_native_text_test.pdf — confirm native PDF extraction and OCR bypass.
09_scanned_fire_certificate.png and 10_scanned_fire_certificate.pdf — real OCR smoke test.
11_blurry_clarity_test.png — clarity detection test; result depends on implementation.
12_scanned_missing_field.png — OCR and missing-field test.

SUGGESTED FULL WORKFLOW
1. Use a dedicated test application for Sunrise Institute of Technology.
2. Upload 01 or 09/10 as an applicant; inspect OCR, classification, clarity, and evidence.
3. Upload 02 and 03 to test document types and date handling.
4. Pair 04 with an application whose ID differs from APP-DEMO-1001 to test reconciliation.
5. Upload 05 or 12 to test missing-field handling.
6. As an officer, inspect all three layers, request clarification, then resubmit a replacement.
7. Confirm old versions and audit events remain, record a final decision, and inspect the PDF report.
8. Record actual observed PASS/FAIL/BLOCKED outcomes; do not assume findings exist unless configured rules produce them.

OFFICIAL REFERENCE (reference only; these demo files are not official templates):
AICTE Approval Process Handbook 2024–2027
https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf
