from app.document_processing.field_extractor import FieldExtractor, parse_date
from app.document_processing.intelligence_types import PageText


def test_parse_date_unambiguous():
    assert parse_date("15-03-2024") == "2024-03-15"
    assert parse_date("2024-03-15") == "2024-03-15"


def test_parse_date_ambiguous_range_returns_none():
    assert parse_date("2024-01-01 to 2024-12-31") is None


def test_extract_key_value_and_preserve_leading_zeros():
    pages = [
        PageText(
            page_number=1,
            text="Institution Name: Demo College\nRegistration Number: 001234\nIssue Date: 01-01-2024\n",
            source="pdf_text",
            char_count=80,
        )
    ]
    fields = FieldExtractor().extract_from_pages(pages, file_name="affidavit.pdf")
    by_name = {f.field_name: f for f in fields}
    assert by_name["institution_name"].raw_value == "Demo College"
    assert by_name["registration_number"].raw_value == "001234"
    assert by_name["registration_number"].normalized_value == "001234"
    assert by_name["issue_date"].normalized_value == "2024-01-01"
    # Regex matches must not invent confidence
    assert by_name["institution_name"].confidence is None


def test_conflicting_dates_marked():
    pages = [
        PageText(
            page_number=1,
            text="Valid Until: 01-01-2024\nValid Until: 01-01-2025\n",
            source="pdf_text",
            char_count=40,
        )
    ]
    fields = FieldExtractor().extract_from_pages(pages)
    valid = [f for f in fields if f.field_name == "valid_until"]
    assert len(valid) >= 2
