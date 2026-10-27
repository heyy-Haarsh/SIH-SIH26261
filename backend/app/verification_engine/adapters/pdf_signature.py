"""PDF digital-signature adapter — prefers pyHanko path, falls back to sigflags."""

from __future__ import annotations

from app.verification_engine.adapters.types import AdapterContext, AdapterResult


def verify_pdf_signature(ctx: AdapterContext) -> AdapterResult:
    from app.verification_engine.adapters.pdf_signature_pyhanko import verify_pdf_signature_pyhanko

    return verify_pdf_signature_pyhanko(ctx)
