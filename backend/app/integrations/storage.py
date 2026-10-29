"""Local filesystem document storage (the only implemented storage backend)."""

from pathlib import Path

from app.core.config import settings
from app.core.errors import PramanError

# Extra roots to search when the configured UPLOAD_DIR does not contain the file
# (common after TestClient runs share the demo DB but point UPLOAD_DIR at tests/_test_uploads).
_FALLBACK_ROOTS = (
    Path(__file__).resolve().parents[2] / "uploads",
    Path(__file__).resolve().parents[2] / "tests" / "_test_uploads",
)


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


def _copy_into_root(src: Path, base: Path) -> Path | None:
    """Copy src into base, preserving relative path when possible; fall back to basename."""
    try:
        base.mkdir(parents=True, exist_ok=True)
        try:
            rel = src.resolve().relative_to(base.resolve())
            dest = base / rel
        except ValueError:
            # Prefer keeping nested structure under a known fallback root
            dest = None
            for fb in _FALLBACK_ROOTS:
                try:
                    rel = src.resolve().relative_to(fb.resolve())
                    dest = base / rel
                    break
                except ValueError:
                    continue
            if dest is None:
                dest = base / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            dest.write_bytes(src.read_bytes())
        return dest.resolve()
    except OSError:
        return None


def _iter_search_roots(base: Path) -> list[Path]:
    roots: list[Path] = [base]
    for fb in _FALLBACK_ROOTS:
        try:
            resolved = fb.resolve()
        except OSError:
            continue
        if resolved not in roots and resolved.is_dir():
            roots.append(resolved)
    return roots


def resolve_upload_file(storage_path: str, root: Path | None = None) -> Path | None:
    """Locate a stored upload. Accepts relative names or absolute paths.

    If the DB points at a legacy/test directory but the basename exists (or can be
    copied) under the configured upload root, return that file so previews work.
    Also searches sibling upload/test upload directories used by the demo DB.
    """
    base = (root or settings.upload_path).resolve()
    raw = Path(storage_path or "")
    if not storage_path:
        return None

    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
        candidates.append(base / raw.name)
    else:
        candidates.append(base / raw)
        candidates.append(Path(storage_path))

    for search_root in _iter_search_roots(base):
        if raw.is_absolute():
            candidates.append(search_root / raw.name)
        else:
            candidates.append(search_root / raw)
            candidates.append(search_root / raw.name)

    seen: set[Path] = set()
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_file():
            continue
        if base == resolved or base in resolved.parents:
            return resolved
        # Recover files written into tests/_test_uploads (or similar) while sharing the demo DB.
        copied = _copy_into_root(resolved, base)
        if copied is not None:
            return copied

    # Last resort: basename search one level deep under fallback roots (demo flat names).
    name = raw.name
    if name:
        for search_root in _iter_search_roots(base):
            direct = search_root / name
            if direct.is_file():
                if base in direct.resolve().parents or base == direct.resolve():
                    return direct.resolve()
                copied = _copy_into_root(direct, base)
                if copied is not None:
                    return copied
            # One nested level: search_root/*/<name>
            try:
                for child in search_root.iterdir():
                    if not child.is_dir():
                        continue
                    nested = child / name
                    if nested.is_file():
                        copied = _copy_into_root(nested, base)
                        if copied is not None:
                            return copied
            except OSError:
                continue
    return None
