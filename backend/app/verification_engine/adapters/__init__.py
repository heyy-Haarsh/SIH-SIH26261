"""Layer 2 verification adapters registry."""

from app.verification_engine.adapters.registry import get_adapter, list_adapter_ids

__all__ = ["get_adapter", "list_adapter_ids"]
