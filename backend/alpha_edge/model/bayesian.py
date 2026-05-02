"""Bayesian update: combine statistical prior with sentiment likelihood.

PRD section 5.2 key principle: sentiment is not additive, it updates a Bayesian prior.
PRD section 14:  P(outcome | evidence) ∝ P(evidence | outcome) × P(outcome)
"""
from __future__ import annotations

import math


def bayes_update(prior: float, likelihood_ratio: float) -> float:
    """Update a probability given a Bayes factor (likelihood ratio).

    likelihood_ratio = P(evidence | outcome=YES) / P(evidence | outcome=NO).
    Values > 1 push the posterior toward YES; < 1 toward NO.
    """
    if not 0.0 < prior < 1.0:
        raise ValueError("prior must be in (0, 1)")
    prior_odds = prior / (1.0 - prior)
    posterior_odds = prior_odds * likelihood_ratio
    return posterior_odds / (1.0 + posterior_odds)


def log_odds(p: float) -> float:
    return math.log(p / (1.0 - p))


def from_log_odds(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))
