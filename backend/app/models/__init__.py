"""Importing this package registers every model on ``Base.metadata``."""

from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.audit_chain import AuditChainEvent
from app.models.category import ApplicationCategory
from app.models.category_config import (
    CategoryConfigVersion,
    DocumentRequirement,
    RequirementRule,
    RequirementRuleVersion,
    RuleCheckResult,
)
from app.models.doc_verification import DocumentVerificationCheck, DocumentVerificationRun
from app.models.document import Document, DocumentVersion, ExtractedField
from app.models.extraction import ExtractionRun
from app.models.forensics import ForensicsEvidence, ForensicsIndicator, ForensicsRun
from app.models.finding_transition import DeficiencyFinding, FindingTransition
from app.models.handbook import HandbookReference
from app.models.notification import Notification
from app.models.reconciliation import ReconciliationItem, ReconciliationRun, ReconciliationValue
from app.models.review import DeficiencyNotice, DeficiencyResponse, ReviewDecision
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.settings import SystemSetting
from app.models.user import Institution, User
from app.models.validation import Finding, FindingEvidence, ValidationRun
from app.models.verification import VerificationRequest

__all__ = [
    "Application",
    "ApplicationCategory",
    "AuditChainEvent",
    "AuditEvent",
    "CategoryConfigVersion",
    "DocumentRequirement",
    "RequirementRule",
    "RequirementRuleVersion",
    "RuleCheckResult",
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
    "DeficiencyFinding",
    "FindingTransition",
    "HandbookReference",
    "Notification",
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
