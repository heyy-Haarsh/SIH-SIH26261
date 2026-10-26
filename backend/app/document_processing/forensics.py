"""Module 8: forensics / authenticity analysis.

Not implemented. This module exists so the pipeline reports the gap honestly
instead of silently skipping it. No tamper, signature, QR, or pixel analysis is performed.
"""

from typing import Optional

from app.document_processing.interfaces import ForensicsModule
from app.document_processing.types import ModuleResult, ModuleStatus


class UnavailableForensicsModule(ForensicsModule):
    name = "forensics"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.UNAVAILABLE,
            message="Tamper / digital-signature / QR forensic analysis is not available in this deployment.",
        )

    def analyze(self, *, file_name: str, content: Optional[bytes] = None) -> ModuleResult:
        return self.capability()
