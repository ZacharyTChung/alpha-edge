"""Team Elo ratings for NBA game win-probability — a FiveThirtyEight-style model.

This is the *independent statistical prior* for the prediction model: a team's
strength derived purely from game results, with no reference to the betting
market. The posterior in `predict.py` starts from this (when available) and the
market price becomes what we compare against — so `edge = elo_prob − market`
is a real disagreement, not a restatement of the market.

Win probability (logistic of the rating gap, base-10, divisor 400):

    P(home beats away) = 1 / (1 + 10^(−(R_home − R_away + HCA) / 400))

Update after a game (K=20, with FiveThirtyEight's margin-of-victory multiplier
so blowouts move ratings more, damped for big favorites to avoid autocorrelation):

    mult  = ln(|margin| + 1) · 2.2 / (0.001 · elo_diff_winner + 2.2)
    shift = K · mult · (actual − expected_winner)
"""
from __future__ import annotations

import math

INITIAL_RATING = 1500.0
K_FACTOR = 20.0
HOME_ADVANTAGE = 100.0  # Elo points; ≈ a 3.5-point home-court edge (538 value)


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score (win probability) of A vs B from the raw rating gap."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def win_probability(rating_home: float, rating_away: float, neutral: bool = False) -> float:
    """P(home team wins), applying home-court advantage unless on a neutral court."""
    hca = 0.0 if neutral else HOME_ADVANTAGE
    return expected_score(rating_home + hca, rating_away)


def _mov_multiplier(margin: int, elo_diff_winner: float) -> float:
    """FiveThirtyEight margin-of-victory multiplier (damped for big favorites)."""
    return math.log(abs(margin) + 1.0) * (2.2 / (0.001 * elo_diff_winner + 2.2))


def update(
    rating_winner: float,
    rating_loser: float,
    margin: int,
    winner_was_home: bool,
    neutral: bool = False,
    k: float = K_FACTOR,
) -> tuple[float, float]:
    """Return (new_winner, new_loser) ratings after one game.

    Zero-sum: the winner gains exactly what the loser loses.
    """
    hca = 0.0 if neutral else HOME_ADVANTAGE
    if winner_was_home:
        diff = (rating_winner + hca) - rating_loser
    else:
        diff = rating_winner - (rating_loser + hca)
    expected_winner = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    shift = k * _mov_multiplier(margin, diff) * (1.0 - expected_winner)
    return rating_winner + shift, rating_loser - shift
