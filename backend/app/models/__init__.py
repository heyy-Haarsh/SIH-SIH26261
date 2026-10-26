"""Importing this package registers every model on ``Base.metadata``."""

from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.category import ApplicationCategory
from app.models.doc_verification import DocumentVerificationCheck, DocumentVerificationRun
from app.models.document import Document, DocumentVersion, ExtractedField
from app.models.extraction import ExtractionRun
from app.models.forensics import ForensicsEvidence, ForensicsIndicator, ForensicsRun
from app.models.reconciliation import ReconciliationItem, ReconciliationRun, ReconciliationValue
from app.models.review import DeficiencyNotice, ReviewDecision
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.settings import SystemSetting
from app.models.user import Institution, User
from app.models.validation import Finding, FindingEvidence, ValidationRun
from app.models.verification import VerificationRequest

__all__ = [
    "Application",
    "ApplicationCategory",
    "AuditEvent",
    "DeficiencyNotice",
    "Document",
    "DocumentVerificationCheck",
    "DocumentVerificationRun",
    "DocumentVersion",
    "ExtractedField",
    "ExtractionRun",
    "Finding",
    "FindingEvidence",
    "ForensicsEvidence",
    "ForensicsIndicator",
    "ForensicsRun",
    "Institution",
    "ReconciliationItem",
    "ReconciliationRun",
    "ReconciliationValue",
    "RegulatoryRule",
    "ReviewDecision",
    "RuleVersion",
    "SystemSetting",
    "User",
    "ValidationRun",
    "VerificationRequest",
]
