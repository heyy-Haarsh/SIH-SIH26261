"""Plain-language wording for findings and verification checks.

Engine titles/descriptions are written for developers ("[SYNTHETIC] ...", rule codes). The scrutiny
UI and the PDF report use these helpers instead. Nothing here asserts authenticity or fraud.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SYNTHETIC_RE = re.compile(r"^\s*\[SYNTHETIC\]\s*", re.IGNORECASE)


@dataclass(frozen=True)
class IssueText:
    title: str
    explanation: str
    applicant_action: str | None
    layer: str  # intake | classification | layer1 | layer2 | cross_document | layer3
    source: str  # rule | file | classification | reconciliation | forensics | document_rule | external
    topic: str  # dedupe topic


def clean(text: str | None) -> str:
    return _SYNTHETIC_RE.sub("", (text or "").strip())


def humanize_field(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").replace("_", " ")).strip().lower()


def _after_colon(title: str) -> str:
    return title.split(":", 1)[1].strip() if ":" in title else title


def describe_finding(
    rule_code: str | None, title: str, description: str, document_name: str | None
) -> IssueText:
    code = (rule_code or "").upper()
    title = clean(title)
    desc = clean(description)
    target = _after_colon(title)

    if code == "SYN-RULE-001":
        return IssueText(
            title=f"Required document not uploaded: {target}",
            explanation=f"The application category requires '{target}', but no file has been uploaded for it.",
            applicant_action=f"Upload '{target}'.",
            layer="layer1",
            source="rule",
            topic=f"missing:{target.lower()}",
        )
    if code == "SYN-RULE-002":
        return IssueText(
            title=title.replace("File type not permitted for", "Wrong file type for"),
            explanation=desc,
            applicant_action="Upload the document again in one of the accepted file types.",
            layer="intake",
            source="file",
            topic=f"file_type:{(document_name or '').lower()}",
        )
    if code == "SYN-RULE-003":
        lowered = title.lower()
        if "soon" in lowered:
            action = "Check the validity date and arrange renewal before it lapses."
            expl = desc
        else:
            action = "Provide a current, valid copy of this document."
            expl = (
                desc
                if "file name" not in desc.lower()
                else "The file name suggests this is an expired or outdated copy."
            )
        return IssueText(
            title=title,
            explanation=expl,
            applicant_action=action,
            layer="layer1",
            source="rule",
            topic=f"validity:{(document_name or '').lower()}:{'soon' if 'soon' in lowered else 'expired'}",
        )
    if code == "SYN-RULE-004":
        return IssueText(
            title=title.replace("File advisory:", "File quality notice:").strip(),
            explanation=desc,
            applicant_action="If the file is damaged or low quality, upload a clean copy.",
            layer="intake",
            source="file",
            topic=f"advisory:{title.lower()}",
        )
    if code == "SYN-RULE-005":
        return IssueText(
            title="The same file was uploaded for more than one requirement",
            explanation=desc,
            applicant_action="Upload the correct, separate document for each requirement.",
            layer="layer1",
            source="rule",
            topic="duplicate_file",
        )
    if code in ("SYN-RULE-006", "SYN-RULE-CLASS-001"):
        return IssueText(
            title=f"Document may be the wrong type: {document_name or target}",
            explanation=(
                "The content or file name of this upload does not look like the document required "
                "here. This is a consistency signal for the officer, not a finding of wrongdoing."
            ),
            applicant_action=(
                "Check that the file uploaded for this requirement is the correct document; "
                "upload the right one if it is not."
            ),
            layer="classification",
            source="classification",
            topic="type_mismatch",
        )
    if code == "SYN-RULE-007" and "duplicate" in title.lower():
        return IssueText(
            title="The same file appears under more than one requirement",
            explanation=desc,
            applicant_action="Upload the correct, separate document for each requirement.",
            layer="cross_document",
            source="reconciliation",
            topic="recon:duplicate_documents",
        )
    if code == "SYN-RULE-007":
        is_missing = "missing" in title.lower()
        return IssueText(
            title=title,
            explanation=desc or "Values differ between documents.",
            applicant_action=(
                "Make sure this detail appears in every document that should state it."
                if is_missing
                else "Confirm which value is correct and correct the document that has the wrong value."
            ),
            layer="cross_document",
            source="reconciliation",
            topic=f"recon:{title.lower()}",
        )
    if code.startswith("SYN-RULE-FOR"):
        return IssueText(
            title=title,
            explanation=desc,
            applicant_action=None,
            layer="layer3",
            source="forensics",
            topic=f"forensics:{title.lower()}",
        )
    return IssueText(
        title=title,
        explanation=desc,
        applicant_action=None,
        layer="layer1",
        source="rule",
        topic=f"{code}:{title.lower()}",
    )


def describe_check(
    check_code: str, title: str, detail: str, document_name: str, layer: str
) -> IssueText:
    """Wording for a Layer 1 / Layer 2 document-verification check."""
    code = (check_code or "").upper()
    title = clean(title)
    detail = clean(detail)
    doc = document_name or "this document"

    if layer == "layer2_external":
        return IssueText(
            title="Official-source verification not completed",
            explanation=(
                "No authorised external source confirmed this document. Passing the local rules "
                "does not prove it is genuine, so the officer must verify it manually."
            ),
            applicant_action=None,
            layer="layer2",
            source="external",
            topic="l2:unverified",
        )

    field = ""
    for prefix in (
        "FORMAT_MISSING_",
        "DATE_AMBIGUOUS_",
        "DATE_FUTURE_",
        "DATE_EXPIRED_",
        "DATE_TOO_OLD_",
        "MISSING_",
        "FORMAT_",
    ):
        if code.startswith(prefix):
            field = humanize_field(code[len(prefix):])
            break

    action: str | None
    if code.startswith("MISSING_") or code.startswith("FORMAT_MISSING_"):
        action = f"Make sure the {field} is clearly shown in {doc}, then upload it again."
    elif code.startswith("FORMAT_"):
        action = f"Correct the {field} in {doc} so it follows the expected format."
    elif code.startswith("DATE_EXPIRED_"):
        action = f"Provide a current copy of {doc}; the {field} has passed."
    elif code.startswith("DATE_FUTURE_"):
        action = f"Check the {field} in {doc}; it is in the future."
    elif code.startswith("DATE_TOO_OLD_"):
        action = f"Provide a more recent copy of {doc}."
    elif code.startswith("DATE_AMBIGUOUS_"):
        action = f"Write the {field} unambiguously (for example 12 March 2024) and re-upload."
    elif code.startswith("DATE_ORDER_"):
        action = f"Correct the dates in {doc} so they are in a logical order."
    elif code == "DOC_UNREADABLE":
        action = f"Upload a clearer, fully readable copy of {doc}."
    elif code == "COORD_PAIR_INCOMPLETE":
        action = f"Provide both latitude and longitude in {doc}."
    elif code.endswith("_REQUIRE_MISSING"):
        action = f"Add the missing details to {doc} and upload it again."
    elif code.endswith("_FAIL"):
        action = f"Check the figures in {doc}; they do not agree with each other."
    else:
        action = None

    return IssueText(
        title=title,
        explanation=detail or title,
        applicant_action=action,
        layer="layer1",
        source="document_rule",
        topic=f"l1:{code}",
    )
