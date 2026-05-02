from alpha_edge.db.models import SignalTier
from alpha_edge.market.edge import classify_tier


def test_tier_thresholds() -> None:
    assert classify_tier(0.20) == SignalTier.STRONG
    assert classify_tier(0.10) == SignalTier.STRONG
    assert classify_tier(0.05) == SignalTier.LEAN
    assert classify_tier(0.0) == SignalTier.NONE
    assert classify_tier(-0.05) == SignalTier.NONE
    assert classify_tier(-0.15) == SignalTier.FADE
