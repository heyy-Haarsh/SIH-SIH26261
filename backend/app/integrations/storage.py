"""Local filesystem document storage (the only implemented storage backend)."""

from pathlib import Path

from app.core.config import settings
from app.core.errors import PramanError


class LocalStorage:
    def __init__(self, root: Path | None = None):
        self.root = (root or settings.upload_path).resolve()

    def save(self, *, application_id: str, document_id: str, version: int, extension: str, content: bytes) -> str:
        """Write the file under uploads/<app>/<doc>/ and return the path relative to the root.

        The stored name is generated server-side; the client file name is never used on disk.
        """
        rel = Path(application_id) / document_id / f"v{version}.{extension}"
        target = (self.root / rel).resolve()
        if self.root not in target.parents:
            raise PramanError("Invalid storage path.", status_code=400, code="invalid_path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return rel.as_posix()

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).is_file()


def get_storage() -> LocalStorage:
    return LocalStorage()
