"""Model inference: produce calibrated probability + confidence interval."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Prediction:
    probability: float
    ci_low: float
    ci_high: float
    feature_contributions: dict[str, float]


def predict_market(market_id: str) -> Prediction:
    raise NotImplementedError("Implement in Phase 2")
