"""X / Twitter via syndication.twitter.com — public, no auth, no key.

How it works: syndication.twitter.com/srv/timeline-profile/screen-name/<USER>
is the same URL Twitter uses to render embedded profile widgets on third-party
websites. The page is a Next.js app with all data inlined as a __NEXT_DATA__
JSON blob in the HTML. We parse it directly.

Important: the timeline returned is "popular" sorted by engagement, not strict
chronological. A user's last 100 entries here are spread across years, weighted
toward viral tweets. This is a feature for breaking-news detection (tweets only
appear once they get traction) but means we miss low-engagement recent posts.

Refresh cadence: hit each account at most every 15 minutes — Twitter starts
serving cached / stale responses if you hit syndication faster.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

CACHE_TTL_SECONDS = 900  # 15 min between profile refreshes per Twitter rate-limit
_cache: dict[str, tuple[float, list]] = {}

# High-credibility sports + betting accounts. Edit this list as needed.
SPORTS_ACCOUNTS: list[tuple[str, str, float]] = [
    # (handle, source_key for credibility lookup, override_credibility)
    ("ShamsCharania", "x:shamscharania", 0.95),
    ("WindhorstESPN", "x:windhorst", 0.85),
    ("ChrisBHaynes", "x:haynes", 0.85),
    ("MarcJSpears", "x:spears", 0.85),
    ("Underdog__NBA", "x:underdog", 0.7),
    ("RotoBaller", "x:rotoballer", 0.7),
    ("ESPNStatsInfo", "x:espnstats", 0.8),
    ("AdamSchefter", "x:schefter", 0.95),
    ("Ken_Rosenthal", "x:rosenthal", 0.9),
    ("BettingProsNBA", "x:bettingpros", 0.6),
]

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


@dataclass
class XPost:
    handle: str
    text: str
    url: str
    created_at: str
    favorite_count: int = 0
    retweet_count: int = 0
    matched_terms: list[str] = field(default_factory=list)


def fetch_profile(handle: str, force: bool = False) -> list[XPost]:
    """Fetch a handle's syndicated timeline, cached for CACHE_TTL_SECONDS.

    Twitter rate-limits this endpoint to ~5 hits per IP per few minutes; the
    cache absorbs that so a refresh-loop on Alpha Edge doesn't get throttled.
    """
    now = time.time()
    cached = _cache.get(handle)
    if cached and not force and (now - cached[0] < CACHE_TTL_SECONDS):
        return list(cached[1])

    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 429:
                # Throttled; serve stale cache if we have any, else empty.
                return list(cached[1]) if cached else []
            r.raise_for_status()
    except Exception:
        return list(cached[1]) if cached else []
    m = _NEXT_DATA.search(r.text)
    if not m:
        return list(cached[1]) if cached else []
    try:
        data = json.loads(m.group(1))
        entries = data["props"]["pageProps"]["timeline"]["entries"]
    except Exception:
        return list(cached[1]) if cached else []
    out: list[XPost] = []
    for e in entries:
        try:
            t = e["content"]["tweet"]
            text = t.get("full_text") or t.get("text") or ""
            user = (t.get("user") or {}).get("screen_name") or handle
            id_str = t.get("id_str") or ""
            out.append(
                XPost(
                    handle=user,
                    text=text,
                    url=f"https://x.com/{user}/status/{id_str}" if id_str else "",
                    created_at=t.get("created_at") or "",
                    favorite_count=int(t.get("favorite_count") or 0),
                    retweet_count=int(t.get("retweet_count") or 0),
                )
            )
        except Exception:
            continue
    _cache[handle] = (now, out)
    return out


def fetch_default(max_age_days: int = 60) -> list[XPost]:
    """Fetch the configured account list; filter to posts within max_age_days."""
    out: list[XPost] = []
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
    for handle, _key, _ in SPORTS_ACCOUNTS:
        try:
            posts = fetch_profile(handle)
        except Exception:
            continue
        for p in posts:
            try:
                ts = datetime.strptime(p.created_at, "%a %b %d %H:%M:%S %z %Y").timestamp()
            except Exception:
                ts = 0
            if ts == 0 or ts >= cutoff:
                out.append(p)
    return out


def credibility_for_handle(handle: str) -> float:
    for h, _key, cred in SPORTS_ACCOUNTS:
        if h.lower() == handle.lower():
            return cred
    return 0.5


_STOPWORDS = {
    "yes", "no", "the", "and", "for", "will", "win", "wins", "winner",
    "game", "match", "vs", "men", "women", "league", "season", "team",
    "tonight", "today", "open", "close", "over", "under", "year", "month",
    "june", "july", "may", "april", "march", "october", "fed", "btc", "eth",
    "america", "american", "united", "states", "world", "national",
}


def match_terms(posts: Iterable[XPost], terms: list[str]) -> list[XPost]:
    multi = [t.lower() for t in terms if " " in t]
    single = [
        t.lower() for t in terms
        if " " not in t and len(t) >= 5 and t.lower() not in _STOPWORDS
    ]
    if not (multi or single):
        return []
    out: list[XPost] = []
    for p in posts:
        hay = p.text.lower()
        m_hits = [n for n in multi if n in hay]
        s_hits = [n for n in single if n in hay]
        if m_hits or s_hits:
            p.matched_terms = m_hits + s_hits
            out.append(p)
    return out
