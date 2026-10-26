from datetime import datetime
from typing import Optional

from app.models.enums import FindingSeverity, FindingStatus, ValidationOutcome
from app.schemas.base import CamelModel


class FindingEvidenceOut(CamelModel):
    id: str
    description: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page_reference: Optional[str] = None
    rule_id: Optional[str] = None
    rule_version: Optional[str] = None


class FindingOut(CamelModel):
    id: str
    title: str
    description: str
    severity: FindingSeverity
    status: FindingStatus
    outcome: ValidationOutcome
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    rule_version: Optional[str] = None
    handbook_ref: Optional[str] = None
    document_id: Optional[str] = None
    evidence: list[FindingEvidenceOut] = []
    created_at: datetime
