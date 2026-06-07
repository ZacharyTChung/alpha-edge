"""Closing-line value (CLV) — the honest backtest of whether the model has edge.

CLV asks: did the price the model would have bet at beat the *closing* price?
A model with real predictive signal systematically gets better prices than the
close, because the market moves toward the information the model already had.
It's the standard edge metric precisely because, on near-efficient markets, raw
win/loss is too noisy and the closing line is the best available "truth" price.

We measure it from the signal history of each market:
  - entry  = the first signal whose model probability disagreed with the market
             by at least `min_edge` (the price we'd have acted on)
  - close  = the last signal before the market closed (the closing line)
  - CLV    = how far the market moved *toward* the model's side, entry → close

Positive mean CLV (and a >50% beat-the-close rate) is the signal that the
model's edges are real rather than noise. Resolution outcomes, where available,
add a Brier score for calibration.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Clv:
    entry_market_p: float
    close_market_p: float
    direction: int        # +1 = model favored YES, -1 = favored NO
    clv_pp: float         # market move toward the bet, in probability points (signed)
    beat_close: bool      # did the line move in our favor at all?
    n_signals: int


def clv_for_signals(signals: list, min_edge: float = 0.03) -> Clv | None:
    """Compute CLV from one market's chronological signals.

    `signals` must be ordered oldest→newest and expose `.market_price` and
    `.model_probability`. Returns None when there's no actionable entry or fewer
    than two distinct price points to compare.
    """
    if len(signals) < 2:
        return None
    entry = next(
        (s for s in signals if abs(s.model_probability - s.market_price) >= min_edge),
        None,
    )
    if entry is None:
        return None
    close = signals[-1]
    if close is entry:
        return None
    direction = 1 if (entry.model_probability - entry.market_price) > 0 else -1
    move = (close.market_price - entry.market_price) * direction
    return Clv(
        entry_market_p=entry.market_price,
        close_market_p=close.market_price,
        direction=direction,
        clv_pp=round(move * 100.0, 2),
        beat_close=move > 0.0,
        n_signals=len(signals),
    )


def brier_score(prob_yes: float, outcome_yes: bool) -> float:
    """Squared error of the YES probability against the realized outcome (0..1)."""
    return (prob_yes - (1.0 if outcome_yes else 0.0)) ** 2
