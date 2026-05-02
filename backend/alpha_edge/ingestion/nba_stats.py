"""NBA Stats API ingestion — official, free.

PRD reference: section 5.1 (Layer 1 — Historical Data Ingestion).
Pulls per-game box scores, advanced metrics, contextual factors.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_edge.config import get_settings

NBA_STATS_BASE = "https://stats.nba.com/stats"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(path: str, params: dict[str, str | int]) -> dict:
    headers = {
        "User-Agent": get_settings().nba_stats_user_agent,
        "Referer": "https://www.nba.com/",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{NBA_STATS_BASE}/{path}", params=params, headers=headers)
        response.raise_for_status()
        return response.json()


def fetch_player_game_log(player_id: int, season: str) -> Iterable[dict]:
    """Yield per-game stat rows for a player and season (e.g. season='2024-25')."""
    raise NotImplementedError("Wire to NBA Stats playergamelog endpoint in Phase 1")


def fetch_team_advanced(team_id: int, season: str) -> Iterable[dict]:
    raise NotImplementedError("Wire to NBA Stats team advanced endpoint in Phase 1")


def fetch_games_for_date(target: date) -> Iterable[dict]:
    raise NotImplementedError("Wire to NBA Stats scoreboard endpoint in Phase 1")
