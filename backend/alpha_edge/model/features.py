"""Feature engineering for the statistical layer.

Builds rolling-window features from PlayerGameStats: trailing average points,
usage rate, opponent-adjusted scoring, rest-day deltas, home/away splits.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeatureRow:
    player_id: str
    market_id: str
    features: dict[str, float]
    label: int | None


def build_player_market_features(player_id: str, market_id: str) -> FeatureRow:
    raise NotImplementedError("Implement in Phase 2")
