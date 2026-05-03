"""Kelly bet sizing.

Two surfaces:
- `kelly_fraction(probability, market_price, fraction)` — generic fractional Kelly
- `half_kelly_capped(probability, market_price, cap)` — v2.0 spec: half-Kelly
  with a hard cap on bankroll fraction (default 3% / 0.03)

PRD section 14:  f* = (b·p − q) / b ;  b = decimal_odds − 1
"""
from __future__ import annotations

KELLY_DEFAULT_FRACTION = 0.5         # half-Kelly per v2.0
KELLY_DEFAULT_CAP = 0.03             # 3% of bankroll, also per v2.0


def kelly_fraction(probability: float, market_price: float, fraction: float = 0.25) -> float:
    """Return the optimal bet fraction of bankroll, clamped at zero.

    market_price is the YES price in [0, 1]. Decimal odds = 1 / market_price.
    `fraction` lets you trade off variance for growth: 1.0 = full Kelly,
    0.5 = half-Kelly, 0.25 = quarter-Kelly.
    """
    if not 0.0 < market_price < 1.0:
        raise ValueError("market_price must be in (0, 1)")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    b = (1.0 / market_price) - 1.0
    q = 1.0 - probability
    full = (b * probability - q) / b
    return max(0.0, fraction * full)


def half_kelly_capped(
    probability: float,
    market_price: float,
    cap: float = KELLY_DEFAULT_CAP,
) -> dict:
    """Half-Kelly bet size capped at `cap` fraction of bankroll (default 3%).

    Returns a dict so callers can show both the uncapped and capped values:
        {
          'b': decimal_odds - 1,
          'full_kelly': f*,
          'half_kelly': 0.5 * f*,
          'capped': min(0.5 * f*, cap),       # what we actually recommend
          'was_capped': bool,
        }

    A capped recommendation means the model edge is so large that uncapped
    Kelly would risk too much — sometimes a sign the model is overconfident.
    """
    if not 0.0 < market_price < 1.0 or not 0.0 <= probability <= 1.0:
        return {"b": 0.0, "full_kelly": 0.0, "half_kelly": 0.0, "capped": 0.0, "was_capped": False}

    b = (1.0 / market_price) - 1.0
    if b <= 0:
        return {"b": b, "full_kelly": 0.0, "half_kelly": 0.0, "capped": 0.0, "was_capped": False}

    q = 1.0 - probability
    full = (b * probability - q) / b
    full = max(0.0, full)
    half = 0.5 * full
    capped_value = min(half, max(0.0, cap))
    return {
        "b": b,
        "full_kelly": full,
        "half_kelly": half,
        "capped": capped_value,
        "was_capped": half > cap,
    }
