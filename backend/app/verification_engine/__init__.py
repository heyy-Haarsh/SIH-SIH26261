"""Configuration-driven three-layer document verification engine (Phase 7)."""

from app.verification_engine.loader import get_config_for_requirement, list_configs
from app.verification_engine.pipeline import run_for_application, run_for_document

__all__ = [
    "get_config_for_requirement",
    "list_configs",
    "run_for_application",
    "run_for_document",
]
