"""Module 1: file intake - genuine local validation (no AI involved).

Checks: file name sanitisation, extension whitelist, empty file, size limit,
content signature sniffing (magic bytes) vs extension, declared content-type
consistency, SHA-256 checksum, light PDF advisories.
"""

import hashlib
import io
import re
import zipfile
from typing import Optional

from app.core import runtime_config
from app.document_processing.interfaces import IntakeModule
from app.document_processing.types import (
    FileCheck,
    FileWarning,
    IntakeResult,
    ModuleResult,
    ModuleStatus,
)

# extension -> (detected kind, canonical mime)
EXTENSION_KINDS: dict[str, tuple[str, str]] = {
    "pdf": ("pdf", "application/pdf"),
    "png": ("png", "image/png"),
    "jpg": ("jpeg", "image/jpeg"),
    "jpeg": ("jpeg", "image/jpeg"),
    "docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "txt": ("text", "text/plain"),
}

_GENERIC_TYPES = {"application/octet-stream", "binary/octet-stream", ""}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
MAX_FILENAME_LEN = 150


def sanitize_file_name(name: Optional[str]) -> str:
    """Strip any directory components and control characters (path traversal safe)."""
    if not name:
        return ""
    base = name.replace("\\", "/").split("/")[-1]
    base = _CONTROL_CHARS.sub("", base).strip().strip(".")
    if len(base) > MAX_FILENAME_LEN:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: MAX_FILENAME_LEN - len(ext) - 1] + dot + ext) if dot else base[:MAX_FILENAME_LEN]
    return base


def sniff_kind(content: bytes) -> str:
    """Detect content kind from magic bytes; returns pdf|png|jpeg|docx|zip|text|unknown."""
    head = content[:16]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = set(zf.namelist())
            if "word/document.xml" in names and "[Content_Types].xml" in names:
                return "docx"
        except zipfile.BadZipFile:
            return "unknown"
        return "zip"
    if content and b"\x00" not in content[:8192]:
        chunk = content[:65536]
        try:
            chunk.decode("utf-8")
            return "text"
        except UnicodeDecodeError as exc:
            # A multibyte character may be cut at the sniffing boundary.
            if len(content) > len(chunk) and exc.start >= len(chunk) - 3:
                return "text"
    return "unknown"


def _pdf_page_count(content: bytes) -> Optional[int]:
    count = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", content))
    return count or None


class LocalIntakeModule(IntakeModule):
    name = "intake"

    def __init__(self, allowed_extensions: Optional[frozenset[str]] = None, max_bytes: Optional[int] = None):
        # Administrator policy may only tighten the deployment limits (see core.runtime_config).
        self.allowed = allowed_extensions if allowed_extensions is not None else runtime_config.allowed_extensions()
        self.max_bytes = max_bytes if max_bytes is not None else runtime_config.max_upload_bytes()

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message="Local file validation: extension, size, content signature, SHA-256.",
        )

    def inspect(
        self, *, file_name: Optional[str], declared_content_type: Optional[str], content: bytes
    ) -> IntakeResult:
        safe_name = sanitize_file_name(file_name)
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        size = len(content)
        sha = hashlib.sha256(content).hexdigest()
        kind_for_ext = EXTENSION_KINDS.get(ext)
        detected = sniff_kind(content) if content else "unknown"
        declared = (declared_content_type or "").split(";")[0].strip().lower() or None

        result = IntakeResult(
            accepted=False,
            file_name=safe_name,
            extension=ext,
            size_bytes=size,
            sha256=sha,
            declared_content_type=declared,
            detected_type=detected,
            mime_type=kind_for_ext[1] if kind_for_ext else "application/octet-stream",
        )

        def reject(status: int, code: str, reason: str) -> IntakeResult:
            result.rejection_status = status
            result.rejection_code = code
            result.rejection_reason = reason
            return result

        # 1. file name
        name_ok = bool(safe_name) and bool(ext)
        result.checks.append(
            FileCheck("file_name", name_ok, f"Sanitised file name: '{safe_name}'" if name_ok else "Missing file name or extension", True)
        )
        if not name_ok:
            return reject(400, "invalid_file_name", "File name and extension are required.")

        # 2. extension whitelist
        ext_ok = ext in self.allowed and kind_for_ext is not None
        result.checks.append(
            FileCheck(
                "extension_allowed",
                ext_ok,
                f"Extension '.{ext}' " + ("is allowed" if ext_ok else f"is not allowed (allowed: {', '.join(sorted(self.allowed))})"),
                True,
            )
        )
        if not ext_ok:
            return reject(415, "unsupported_file_type", f"File type '.{ext}' is not allowed. Allowed: {', '.join(sorted(self.allowed))}.")

        # 3. empty
        non_empty = size > 0
        result.checks.append(FileCheck("not_empty", non_empty, "File has content" if non_empty else "File is empty", True))
        if not non_empty:
            return reject(400, "empty_file", "Uploaded file is empty.")

        # 4. size
        size_ok = size <= self.max_bytes
        limit_mb = self.max_bytes / (1024 * 1024)
        result.checks.append(
            FileCheck("size_limit", size_ok, f"{size} bytes (limit {limit_mb:g} MB)" if size_ok else f"Exceeds {limit_mb:g} MB limit", True)
        )
        if not size_ok:
            return reject(413, "file_too_large", f"File exceeds the {limit_mb:g} MB size limit.")

        # 5. content signature must match extension
        expected_kind = kind_for_ext[0]
        sig_ok = detected == expected_kind
        result.checks.append(
            FileCheck(
                "content_signature",
                sig_ok,
                f"Content detected as '{detected}', matches '.{ext}'" if sig_ok else f"Content detected as '{detected}' but extension is '.{ext}'",
                True,
            )
        )
        if not sig_ok:
            return reject(415, "content_mismatch", f"File content does not match the '.{ext}' extension (detected: {detected}).")

        # 6. declared content type (advisory)
        expected_mime = kind_for_ext[1]
        if declared and declared not in _GENERIC_TYPES and declared != expected_mime:
            msg = f"Client declared '{declared}' but content is '{expected_mime}'."
            result.warnings.append(FileWarning("declared_type_mismatch", msg))
            result.checks.append(FileCheck("declared_content_type", False, msg, False))
        else:
            result.checks.append(FileCheck("declared_content_type", True, "Declared content type is consistent or unspecified", False))

        # 7. checksum (informational)
        result.checks.append(FileCheck("sha256", True, sha, False))

        # 8. PDF advisories
        if detected == "pdf":
            result.page_count = _pdf_page_count(content)
            if b"/Encrypt" in content:
                result.warnings.append(FileWarning("pdf_encrypted", "PDF appears to be encrypted; content analysis is not possible."))
            if b"%%EOF" not in content[-2048:]:
                result.warnings.append(FileWarning("pdf_possibly_truncated", "PDF end-of-file marker not found; the file may be truncated."))

        result.accepted = True
        return result
