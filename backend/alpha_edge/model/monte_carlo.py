"""Monte Carlo simulation for continuous-underlying markets.

Example: 'LeBron scores 25+ points' — sample from his scoring distribution
conditioned on context (opponent, rest, home/away) and count threshold breaches.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimResult:
    mean: float
    p_threshold: float
    ci_low: float
    ci_high: float


def simulate_threshold(samples: list[float], threshold: float) -> SimResult:
    raise NotImplementedError("Implement in Phase 2: empirical CI from bootstrap")
