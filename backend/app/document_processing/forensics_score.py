"""Forensics triage score — preliminary indicators only, never 'forged'."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

INTERPRETATION = "preliminary indicator requiring human verification"
_WEIGHTS_PATH = (
    Path(__file__).resolve().parents[1] / "verification_engine" / "configs" / "forensics_weights.json"
)


@dataclass
class SignalScore:
    signal_code: str
    raw_score: float
    weight: float
    contribution: float
    reason: str
    confidence: float
    evidence_region: Optional[str] = None
    interpretation: str = INTERPRETATION


@dataclass
class TriageScore:
    total: float
    signals: list[SignalScore] = field(default_factory=list)
    interpretation: str = INTERPRETATION
    config_version: str = "v1"


def load_weights() -> tuple[str, dict[str, float]]:
    data = json.loads(_WEIGHTS_PATH.read_text(encoding="utf-8"))
    return str(data.get("version") or "v1"), dict(data.get("weights") or {})


def compute_triage_score(
    active_signals: dict[str, float],
    *,
    reasons: dict[str, str] | None = None,
    weights_override: dict[str, float] | None = None,
) -> TriageScore:
    """active_signals: signal_code -> raw_score in [0,1]."""
    version, weights = load_weights()
    if weights_override:
        weights = {**weights, **weights_override}
    reasons = reasons or {}
    signals: list[SignalScore] = []
    total_w = sum(weights.values()) or 1.0
    contrib_sum = 0.0
    for code, weight in weights.items():
        raw = float(active_signals.get(code, 0.0))
        raw = max(0.0, min(1.0, raw))
        contrib = raw * weight
        contrib_sum += contrib
        if raw > 0:
            signals.append(
                SignalScore(
                    signal_code=code,
                    raw_score=raw,
                    weight=weight,
                    contribution=contrib,
                    reason=reasons.get(code, code),
                    confidence=min(0.75, 0.4 + raw * 0.3),
                    interpretation=INTERPRETATION,
                )
            )
    # Scale to 0–100 relative to total weight mass
    total = round((contrib_sum / total_w) * 100.0, 2)
    return TriageScore(total=total, signals=signals, interpretation=INTERPRETATION, config_version=version)
