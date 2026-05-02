"""Basketball Reference scraper.

Used as a fallback for advanced metrics (RAPTOR proxies, BPM, on/off splits).
Respect rate limits and robots.txt.
"""
from __future__ import annotations

from collections.abc import Iterable


def fetch_player_advanced(player_slug: str, season: int) -> Iterable[dict]:
    raise NotImplementedError("Implement in Phase 1: scrape /players/{slug}/gamelog/{season}/advanced")


def fetch_team_on_off(team_abbr: str, season: int) -> Iterable[dict]:
    raise NotImplementedError("Implement in Phase 1: scrape on/off splits")
