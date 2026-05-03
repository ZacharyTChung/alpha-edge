"""Basketball Reference scraper — public, free, rate-limited.

Two surfaces:
1. `recent_gamelog(slug, season)` — last N games for a player as parsed dicts.
   Cached for 1 hour to respect BBRef's 20-req/min rate limit.
2. `match_player(question_text)` — heuristic: scan question text for any of the
   ~80 most-bet-on NBA players from PLAYER_SLUGS and return the first hit's
   slug. Good enough until we wire spaCy NER.
"""
from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

CACHE_TTL_SECONDS = 3600
_cache: dict[str, tuple[float, list]] = {}

# Top NBA players by 2024-25 betting volume / market frequency. Hand-curated so
# we have low-risk exact matches without doing fuzzy NER. Add more as needed.
PLAYER_SLUGS: dict[str, str] = {
    "lebron james": "jamesle01",
    "anthony davis": "davisan02",
    "stephen curry": "curryst01",
    "klay thompson": "thompkl01",
    "draymond green": "greendr01",
    "kevin durant": "duranke01",
    "devin booker": "bookede01",
    "luka doncic": "doncilu01",
    "kyrie irving": "irvinky01",
    "nikola jokic": "jokicni01",
    "jamal murray": "murraja01",
    "aaron gordon": "gordoaa01",
    "michael porter": "porteji01",
    "jayson tatum": "tatumja01",
    "jaylen brown": "brownja02",
    "kristaps porzingis": "porzikr01",
    "jrue holiday": "holidjr01",
    "joel embiid": "embiijo01",
    "tyrese maxey": "maxeyty01",
    "paul george": "georgpa01",
    "giannis antetokounmpo": "antetgi01",
    "damian lillard": "lillada01",
    "khris middleton": "middlkh01",
    "jimmy butler": "butleji01",
    "bam adebayo": "adebaba01",
    "tyler herro": "herroty01",
    "trae young": "youngtr01",
    "dejounte murray": "murrade01",
    "donovan mitchell": "mitchdo01",
    "darius garland": "garlada01",
    "evan mobley": "moblev01",
    "jarrett allen": "allenja01",
    "ja morant": "moranja01",
    "desmond bane": "banede01",
    "jaren jackson": "jacksja02",
    "victor wembanyama": "wembavi01",
    "devin vassell": "vassede01",
    "shai gilgeous-alexander": "gilgesh01",
    "chet holmgren": "holmgch01",
    "jalen williams": "willija06",
    "lauri markkanen": "markkla01",
    "anthony edwards": "edwaran01",
    "karl-anthony towns": "townska01",
    "rudy gobert": "goberru01",
    "mike conley": "conlemi01",
    "alperen sengun": "sengual01",
    "jalen green": "greenja05",
    "jabari smith": "smithja05",
    "fred vanvleet": "vanvlfr01",
    "tyrese haliburton": "halibty01",
    "pascal siakam": "siakapa01",
    "myles turner": "turnemy01",
    "rj barrett": "barrerj01",
    "scottie barnes": "barnesc01",
    "immanuel quickley": "quickim01",
    "deandre ayton": "aytonde01",
    "scoot henderson": "henderso01",
    "anfernee simons": "simonan01",
    "shaedon sharpe": "sharpsh01",
    "domantas sabonis": "sabondo01",
    "deaaron fox": "foxde01",
    "keegan murray": "murrake02",
    "lamelo ball": "ballla01",
    "brandon miller": "millebr02",
    "miles bridges": "bridgmi01",
    "paolo banchero": "bancheba01",
    "franz wagner": "wagnefr01",
    "jalen suggs": "suggsja01",
    "cade cunningham": "cunnica01",
    "jaden ivey": "iveyja01",
    "jalen brunson": "brunsja01",
    "julius randle": "randlju01",
    "josh hart": "hartjo01",
    "mikal bridges": "bridgmi02",
    "og anunoby": "anunoog01",
    "zion williamson": "willizi01",
    "brandon ingram": "ingrabr01",
    "cj mccollum": "mccolcj01",
}

CURRENT_SEASON = 2025


@dataclass
class GameRow:
    date: str
    opponent: str
    home_away: str
    minutes: float
    points: int
    rebounds: int
    assists: int
    fg_pct: float
    plus_minus: int


def match_player(question_text: str) -> tuple[str, str] | None:
    """Return (display_name, slug) for the first matched player, or None."""
    if not question_text:
        return None
    q = question_text.lower()
    for name, slug in PLAYER_SLUGS.items():
        if name in q:
            return (name.title(), slug)
        first_last = name.split()
        if len(first_last) == 2 and first_last[1] in q and first_last[0] in q:
            return (name.title(), slug)
    return None


# BBRef changed data-stat keys post-2024; current schema uses "date" (not date_game),
# "trb_per_game" or "trb" depending on the page, and game_location for home/away.
_PTS_RE = re.compile(r'data-stat="pts"[^>]*>(\d+)<')
_REB_RE = re.compile(r'data-stat="trb"[^>]*>(\d+)<')
_AST_RE = re.compile(r'data-stat="ast"[^>]*>(\d+)<')
_MIN_RE = re.compile(r'data-stat="mp"[^>]*>(\d+):(\d+)<')
_DATE_RE = re.compile(r'data-stat="date"[^>]*>(?:<a[^>]*>)?(\d{4}-\d{2}-\d{2})')
_OPP_RE = re.compile(r'data-stat="opp_name_abbr"[^>]*>(?:<a[^>]*>)?([A-Z]{2,4})')
_LOC_RE = re.compile(r'data-stat="game_location"[^>]*>([@H]?)<')


def recent_gamelog(slug: str, season: int = CURRENT_SEASON, limit: int = 10) -> list[GameRow]:
    """Fetch the most recent `limit` games for a player. Cached 1h."""
    key = f"{slug}:{season}"
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0] < CACHE_TTL_SECONDS):
        return list(cached[1])[:limit]

    url = f"https://www.basketball-reference.com/players/{slug[0]}/{slug}/gamelog/{season}"
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as c:
            r = c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return list(cached[1])[:limit] if cached else []
            html = r.text
    except Exception:
        return list(cached[1])[:limit] if cached else []

    # Row-based parse: only count <tr> rows that are actual game logs
    # (id starts with `player_game_log`). This skips summary, career-total,
    # and league-average rows that otherwise pollute the data.
    rows: list[GameRow] = []
    row_pat = re.compile(
        r'<tr [^>]*id="player_game_log[^"]*"[^>]*>(.*?)</tr>',
        re.DOTALL,
    )
    for row_html in row_pat.findall(html):
        try:
            pm = _PTS_RE.search(row_html)
            rm = _REB_RE.search(row_html)
            am = _AST_RE.search(row_html)
            mm = _MIN_RE.search(row_html)
            dm = _DATE_RE.search(row_html)
            if not (pm and rm and am and mm and dm):
                continue
            points = int(pm.group(1))
            rebounds = int(rm.group(1))
            assists = int(am.group(1))
            # Sanity guard against malformed rows (NBA single-game records:
            # most points 100, rebounds 55, assists 30).
            if points > 100 or rebounds > 55 or assists > 30:
                continue
            mins_part, secs_part = mm.group(1), mm.group(2)
            minutes_played = int(mins_part) + int(secs_part) / 60.0
            opp_match = _OPP_RE.search(row_html)
            loc_match = _LOC_RE.search(row_html)
            rows.append(
                GameRow(
                    date=dm.group(1),
                    opponent=opp_match.group(1) if opp_match else "",
                    home_away="away" if loc_match and loc_match.group(1) == "@" else "home",
                    minutes=round(minutes_played, 1),
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    fg_pct=0.0,
                    plus_minus=0,
                )
            )
        except (TypeError, ValueError):
            continue

    rows.reverse()  # newest first
    _cache[key] = (now, rows)
    return rows[:limit]


def stats_summary(slug: str, name: str, season: int = CURRENT_SEASON, n: int = 10) -> str:
    """Compact text summary suitable for inclusion in an LLM prompt."""
    games = recent_gamelog(slug, season, limit=n)
    if not games:
        return ""
    pts = [g.points for g in games]
    reb = [g.rebounds for g in games]
    ast = [g.assists for g in games]
    mins = [g.minutes for g in games]
    avg = lambda xs: round(sum(xs) / max(1, len(xs)), 1)
    last3_pts = [g.points for g in games[:3]]
    return (
        f"{name} — last {len(games)} games: "
        f"{avg(pts)} PPG / {avg(reb)} RPG / {avg(ast)} APG in {avg(mins)} min. "
        f"Last 3 game points: {', '.join(str(p) for p in last3_pts)}."
    )


def market_stats_context(question_text: str) -> str | None:
    """Return a single-line stats summary for the player named in the question, if any."""
    hit = match_player(question_text)
    if not hit:
        return None
    name, slug = hit
    summary = stats_summary(slug, name)
    return summary or None


def fetch_player_advanced(player_slug: str, season: int) -> Iterable[dict]:
    raise NotImplementedError("Advanced metrics scraper deferred to Phase 2")


def fetch_team_on_off(team_abbr: str, season: int) -> Iterable[dict]:
    raise NotImplementedError("Deferred to Phase 2")
