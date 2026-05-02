"""Kelly sizing.

PRD section 14:  f* = (b·p - q) / b
"""
from __future__ import annotations


def kelly_fraction(probability: float, market_price: float, fraction: float = 0.25) -> float:
    """Return the optimal bet fraction of bankroll, clamped at zero.

    market_price is the YES price in [0, 1]. Decimal odds = 1 / market_price.
    Always use fractional Kelly (default 0.25) to account for model uncertainty.
    """
    if not 0.0 < market_price < 1.0:
        raise ValueError("market_price must be in (0, 1)")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    b = (1.0 / market_price) - 1.0
    q = 1.0 - probability
    full = (b * probability - q) / b
    return max(0.0, fraction * full)
