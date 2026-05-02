"""Source credibility weighting.

Adrian Wojnarowski tweet > anonymous Reddit post. Weights are stored per-source
and updated as the system observes which sources predict correctly.
"""
from __future__ import annotations

DEFAULT_WEIGHTS: dict[str, float] = {
    "twitter:wojespn": 1.0,
    "twitter:shamscharania": 1.0,
    "news:rotowire": 0.9,
    "news:espn": 0.8,
    "reddit:nba": 0.4,
    "reddit:sportsbook": 0.4,
    "reddit:kalshimarkets": 0.3,
}


def credibility_for(source_key: str) -> float:
    return DEFAULT_WEIGHTS.get(source_key.lower(), 0.5)
