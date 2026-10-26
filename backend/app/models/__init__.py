"""Importing this package registers every model on ``Base.metadata``."""

from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.category import ApplicationCategory
from app.models.document import Document, DocumentVersion, ExtractedField
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.user import Institution, User
from app.models.validation import Finding, FindingEvidence, ValidationRun
from app.models.verification import VerificationRequest

__all__ = [
    "Application",
    "ApplicationCategory",
    "AuditEvent",
    "DeficiencyNotice",
    "Document",
    "DocumentVersion",
    "ExtractedField",
    "Finding",
    "FindingEvidence",
    "Institution",
    "RegulatoryRule",
    "ReviewDecision",
    "RuleVersion",
    "User",
    "ValidationRun",
    "VerificationRequest",
]
