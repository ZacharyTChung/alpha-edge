"""Process-cached NBA team Elo ratings, built by replaying the season's results.

Ratings are derived purely from game outcomes (`nba_stats.fetch_team_game_results`)
and held in memory, rebuilt at most every few hours. `prob_for_market` maps a
Kalshi NBA game market to the Elo win probability of its YES team, parsing the
two team codes and home/away straight from the ticker (e.g. ...-26JUN08SASNYK-NYK
→ away SAS @ home NYK, YES = NYK). Anything we can't resolve returns None so the
caller falls back to the de-vigged market price.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from alpha_edge.ingestion import nba_stats
from alpha_edge.model import elo

logger = logging.getLogger(__name__)

_ratings: dict[str, float] = {}
_built_at: datetime | None = None

_MATCHUP_RE = re.compile(r"([A-Z]{6})$")


def _current_season() -> str:
    """NBA season string for today, e.g. '2025-26'. Season spans Oct–June."""
    today = datetime.now(timezone.utc)
    start = today.year if today.month >= 10 else today.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _replay(rows: list[dict], ratings: dict[str, float]) -> None:
    """Update `ratings` in place by replaying games (each has two team rows)."""
    by_game: dict[str, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r.get("GAME_ID"), []).append(r)

    def sort_key(item):
        rs = item[1]
        return (rs[0].get("GAME_DATE") or "", item[0] or "")

    for _gid, sides in sorted(by_game.items(), key=sort_key):
        if len(sides) != 2:
            continue
        try:
            home = next(s for s in sides if "vs." in (s.get("MATCHUP") or ""))
            away = next(s for s in sides if "@" in (s.get("MATCHUP") or ""))
            h_abbr, a_abbr = home["TEAM_ABBREVIATION"], away["TEAM_ABBREVIATION"]
            margin = abs(int(home["PTS"]) - int(away["PTS"]))
            if home.get("WL") == "W":
                w_abbr, l_abbr, winner_home = h_abbr, a_abbr, True
            else:
                w_abbr, l_abbr, winner_home = a_abbr, h_abbr, False
        except (StopIteration, KeyError, TypeError, ValueError):
            continue  # skip malformed / in-progress rows
        rw = ratings.get(w_abbr, elo.INITIAL_RATING)
        rl = ratings.get(l_abbr, elo.INITIAL_RATING)
        ratings[w_abbr], ratings[l_abbr] = elo.update(rw, rl, margin, winner_home)


def rebuild() -> None:
    """Rebuild ratings from this season's regular-season + playoff results."""
    global _ratings, _built_at
    season = _current_season()
    fresh: dict[str, float] = {}
    rows: list[dict] = []
    for season_type in ("Regular Season", "Playoffs"):
        try:
            rows.extend(nba_stats.fetch_team_game_results(season, season_type))
        except Exception as e:  # playoffs 404 early in the year, etc.
            logger.info("elo: no %s data for %s (%s)", season_type, season, e)
    _replay(rows, fresh)
    if fresh:
        _ratings = fresh
        _built_at = datetime.now(timezone.utc)
        logger.info("elo: rebuilt %d team ratings for %s", len(fresh), season)


def ensure_fresh(max_age_hours: float = 6.0) -> None:
    """Rebuild if ratings are empty or stale. Never raises — degrades to stale."""
    if _ratings and _built_at is not None:
        if datetime.now(timezone.utc) - _built_at < timedelta(hours=max_age_hours):
            return
    try:
        rebuild()
    except Exception as e:
        logger.warning("elo: rebuild failed, keeping existing ratings (%s)", e)


def get(abbr: str) -> float | None:
    return _ratings.get(abbr)


def prob_for_market(market) -> float | None:
    """Elo win probability for the market's YES team, or None if unresolvable."""
    ext = market.external_id or ""
    if "KXNBAGAME" not in ext:
        return None
    ensure_fresh()  # lazy-load on first NBA market (cheap no-op once warm)
    ticker = ext.split("kalshi:", 1)[-1]
    yes_abbr = ticker.rsplit("-", 1)[-1]
    m = _MATCHUP_RE.search(ticker.rsplit("-", 1)[0])
    if not m:
        return None
    matchup = m.group(1)
    away_abbr, home_abbr = matchup[:3], matchup[3:]
    r_home, r_away = _ratings.get(home_abbr), _ratings.get(away_abbr)
    if r_home is None or r_away is None:
        return None
    p_home = elo.win_probability(r_home, r_away)
    if yes_abbr == home_abbr:
        return p_home
    if yes_abbr == away_abbr:
        return 1.0 - p_home
    return None
