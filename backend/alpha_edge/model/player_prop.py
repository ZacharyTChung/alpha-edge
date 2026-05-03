"""Player-prop projection per Alpha Edge v2.0 spec.

Projection model:
    Base = 0.30·season_median + 0.30·last_20_median + 0.25·last_10_median + 0.15·last_5_median
    Projected_Mean = Base + Matchup + Pace + Usage + Rest + Text + Market
    z = (line - Projected_Mean) / Adjusted_SD
    prob_over = 1 - Φ(z)
    prob_under = Φ(z)

This module implements what we have data for. Where v2.0 needs inputs we don't
yet scrape (opponent defensive rank, opponent pace, line movement history), the
adjustment is set to 0 with a flag so callers know it's a partial projection.

Default SDs by prop_type when we can't compute from history (v2.0 §Operating rules):
    points 6.5, rebounds 2.5, assists 2.0, blocks 0.8, steals 0.9, threes 1.3
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Literal

from alpha_edge.ingestion import basketball_ref as bbref_mod

PropType = Literal["points", "rebounds", "assists", "blocks", "steals", "threes"]
Side = Literal["over", "under"]

DEFAULT_SD: dict[str, float] = {
    "points": 6.5,
    "rebounds": 2.5,
    "assists": 2.0,
    "blocks": 0.8,
    "steals": 0.9,
    "threes": 1.3,
}

# Sensitivity multipliers per v2.0 signal type (how much the text adjustment
# moves the projected mean — in the units of the prop, e.g. points)
TEXT_SENSITIVITY = {
    "confirmed_out": -100.0,           # remove from consideration → NO BET
    "minutes_restriction": -5.5,
    "load_management_risk": -2.0,
    "lineup_change_positive": 3.5,
    "fatigue_signal": -1.5,
    "matchup_narrative": 0.7,
    "default_text": 0.0,
}

# Volatility multiplier for adjusted SD per v2.0
VOL_GAME_TIME_DECISION = 1.35
VOL_BACK_TO_BACK = 1.15
VOL_HIGH_CV = 1.10
VOL_NORMAL = 1.00


@dataclass
class PropParse:
    player_name: str | None
    prop_type: PropType | None
    line: float | None
    side: Side
    raw_text: str

    def is_complete(self) -> bool:
        return self.player_name is not None and self.prop_type is not None and self.line is not None


# ── Question parsing ────────────────────────────────────────────────────────
_PROP_KEYWORDS: dict[str, str] = {
    "point": "points",
    "rebound": "rebounds",
    "assist": "assists",
    "block": "blocks",
    "steal": "steals",
    "three": "threes",
    "3-pt": "threes",
    "3-pointer": "threes",
}


def parse_prop_question(question: str) -> PropParse:
    """Heuristically parse a market question for player + prop_type + line.

    Examples that should match:
      - "LeBron James scores 25+ points tonight?"            → (LeBron James, points, 25, over)
      - "Will Stephen Curry have over 4.5 assists?"          → (Stephen Curry, assists, 4.5, over)
      - "Jokic over 28.5 points vs Lakers?"                  → (Nikola Jokic, points, 28.5, over)
      - "Anthony Edwards: under 22.5 points"                 → (Anthony Edwards, points, 22.5, under)
    """
    text = question or ""
    lower = text.lower()

    # 1. Prop type via keyword
    prop_type: PropType | None = None
    for k, v in _PROP_KEYWORDS.items():
        if k in lower:
            prop_type = v  # type: ignore[assignment]
            break

    # 2. Line — first decimal/integer near a comparator or "X+" pattern
    line: float | None = None
    side: Side = "over"
    if "under" in lower:
        side = "under"
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+", text)
    if m:
        line = float(m.group(1)) - 0.5  # "25+" means hits 25 → line at 24.5 over
    if line is None:
        m = re.search(r"(?:over|under|above|below|>|<)\s*(\d+(?:\.\d+)?)", lower)
        if m:
            line = float(m.group(1))
    if line is None:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            line = float(m.group(1))

    # 3. Player name — match against the BBRef hardcoded slug map
    player_name = None
    for canonical_lower in bbref_mod.PLAYER_SLUGS.keys():
        if canonical_lower in lower:
            player_name = canonical_lower.title()
            break
        # last-name-only fallback (works for unique surnames like "Jokic", "Embiid")
        last = canonical_lower.split()[-1]
        if last in lower and len(last) >= 5:
            player_name = canonical_lower.title()
            break

    return PropParse(
        player_name=player_name,
        prop_type=prop_type,
        line=line,
        side=side,
        raw_text=text,
    )


def is_player_prop(question: str) -> bool:
    return parse_prop_question(question).is_complete()


# ── Projection ──────────────────────────────────────────────────────────────
@dataclass
class Adjustment:
    name: str
    value: float
    note: str = ""


@dataclass
class PlayerPropProjection:
    parse: PropParse
    base: float
    adjustments: list[Adjustment]
    projected_mean: float
    adjusted_sd: float
    z_score: float
    prob_over: float
    prob_under: float
    n_games_used: int
    sd_source: str                # "history" | "default_table"
    flags: dict[str, bool] = field(default_factory=dict)


def _stat_for_prop(g: bbref_mod.GameRow, prop: PropType) -> float:
    return {
        "points": g.points,
        "rebounds": g.rebounds,
        "assists": g.assists,
        "blocks": 0.0,    # bbref scraper doesn't yet pull blocks/steals/threes
        "steals": 0.0,
        "threes": 0.0,
    }.get(prop, 0.0)


def _coerce_pos(x: float, fallback: float) -> float:
    return x if x and x > 0 else fallback


def project(
    parse: PropParse,
    text_signal_type: str = "default_text",
    rest_days: int | None = None,
    is_back_to_back: bool = False,
    is_game_time_decision: bool = False,
) -> PlayerPropProjection | None:
    """Compute a player-prop projection. Returns None if the parse is incomplete
    or we can't get any gamelog data."""
    if not parse.is_complete():
        return None
    assert parse.player_name and parse.prop_type and parse.line is not None

    # Get player slug and gamelog
    slug = bbref_mod.PLAYER_SLUGS.get(parse.player_name.lower())
    if not slug:
        return None
    games = bbref_mod.recent_gamelog(slug, limit=20)
    if not games:
        return None

    values = [_stat_for_prop(g, parse.prop_type) for g in games]
    last_5 = values[:5]
    last_10 = values[:10]
    last_20 = values[:20]

    season_median = statistics.median(values)  # using last_20 as season proxy until we have more
    base = (
        0.30 * season_median
        + 0.30 * statistics.median(last_20)
        + 0.25 * statistics.median(last_10)
        + 0.15 * statistics.median(last_5)
    )

    # Adjustments we have data for
    adjustments: list[Adjustment] = []

    # Rest adjustment
    rest_value = 0.0
    if is_back_to_back:
        rest_value = -2.0
    elif rest_days is not None and rest_days >= 3:
        rest_value = 0.7
    if rest_value:
        adjustments.append(Adjustment("rest", rest_value, f"{rest_days if rest_days is not None else 'b2b'} day(s)"))

    # Text adjustment
    text_value = TEXT_SENSITIVITY.get(text_signal_type, 0.0)
    if text_value:
        adjustments.append(Adjustment("text", text_value, text_signal_type))

    # Adjustments we don't have data for yet (flag, value 0)
    for missing in ("matchup", "pace", "usage", "market_movement"):
        adjustments.append(Adjustment(missing, 0.0, "data not yet ingested"))

    projected_mean = base + sum(a.value for a in adjustments)

    # SD: use historical if we have enough data, else default table
    sd_source = "history"
    if len(values) >= 5:
        try:
            base_sd = statistics.stdev(values)
            if base_sd <= 0.5:  # implausibly low — fall back
                base_sd = DEFAULT_SD.get(parse.prop_type, 5.0)
                sd_source = "default_table"
        except statistics.StatisticsError:
            base_sd = DEFAULT_SD.get(parse.prop_type, 5.0)
            sd_source = "default_table"
    else:
        base_sd = DEFAULT_SD.get(parse.prop_type, 5.0)
        sd_source = "default_table"

    # Volatility multiplier
    mult = VOL_NORMAL
    if is_game_time_decision:
        mult *= VOL_GAME_TIME_DECISION
    if is_back_to_back:
        mult *= VOL_BACK_TO_BACK
    cv = base_sd / max(0.5, base) if base > 0 else 0.0
    if cv > 0.5:
        mult *= VOL_HIGH_CV
    adjusted_sd = base_sd * mult

    z = (parse.line - projected_mean) / max(0.01, adjusted_sd)
    prob_under = _norm_cdf(z)
    prob_over = 1.0 - prob_under

    # If text says confirmed_out, flag
    flags = {
        "confirmed_out": text_signal_type == "confirmed_out",
        "small_sample": len(values) < 15,
        "high_cv": cv > 0.5,
    }

    return PlayerPropProjection(
        parse=parse,
        base=base,
        adjustments=adjustments,
        projected_mean=projected_mean,
        adjusted_sd=adjusted_sd,
        z_score=z,
        prob_over=prob_over,
        prob_under=prob_under,
        n_games_used=len(values),
        sd_source=sd_source,
        flags=flags,
    )


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
