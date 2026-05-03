"""News article ingestion via RSS feeds + light HTML extraction."""
from __future__ import annotations

import re
import socket
from collections.abc import Iterable
from dataclasses import dataclass, field

import feedparser

socket.setdefaulttimeout(8.0)

import urllib.parse

import httpx

# Default sport-leaning feeds. RotoWire is highest-credibility (sports-specialist
# wire reporting on injuries, depth charts, lineup changes) — see credibility.py.
DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("news:rotowire", "https://www.rotowire.com/rss/news.php?sport=NBA"),
    ("news:rotowire", "https://www.rotowire.com/rss/news.php?sport=NFL"),
    ("news:rotowire", "https://www.rotowire.com/rss/news.php?sport=MLB"),
    ("news:espn", "https://www.espn.com/espn/rss/nba/news"),
    ("news:espn", "https://www.espn.com/espn/rss/nfl/news"),
    ("news:espn", "https://www.espn.com/espn/rss/mlb/news"),
    ("news:yahoo", "https://sports.yahoo.com/nba/rss.xml"),
    ("news:cbs", "https://www.cbssports.com/rss/headlines/nba/"),
]


@dataclass
class NewsDoc:
    url: str
    title: str
    body: str
    publish_date: str | None
    source: str
    matched_terms: list[str] = field(default_factory=list)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def fetch_feed(feed_url: str, source_key: str = "news:rss") -> Iterable[NewsDoc]:
    parsed = feedparser.parse(feed_url)
    for entry in parsed.entries:
        yield NewsDoc(
            url=entry.get("link", ""),
            title=_strip_html(entry.get("title", "")),
            body=_strip_html(entry.get("summary", "") or entry.get("description", "")),
            publish_date=entry.get("published") or entry.get("updated"),
            source=source_key,
        )


def fetch_all_default() -> list[NewsDoc]:
    """Fetch all default RSS feeds; failures per feed are silently skipped."""
    out: list[NewsDoc] = []
    for source_key, url in DEFAULT_FEEDS:
        try:
            out.extend(list(fetch_feed(url, source_key)))
        except Exception:
            continue
    return out


def fetch_google_news(query: str, limit: int = 10, when: str = "1d") -> list[NewsDoc]:
    """Per-market query against Google News RSS.

    `when` is Google News's recency operator: "1h", "6h", "1d", "7d". Limits
    results to articles published in that window — critical for betting where
    a 3-day-old "questionable" tag is stale information."""
    if not query:
        return []
    q = urllib.parse.quote_plus(f"{query} when:{when}")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return []
    out: list[NewsDoc] = []
    for entry in parsed.entries[:limit]:
        out.append(NewsDoc(
            url=entry.get("link", ""),
            title=_strip_html(entry.get("title", "")),
            body=_strip_html(entry.get("summary", "") or entry.get("description", "")),
            publish_date=entry.get("published") or entry.get("updated"),
            source="news:google",
            matched_terms=[query],
        ))
    return out


def fetch_google_news_multi(terms: list[str], per_query: int = 4) -> list[NewsDoc]:
    """Run several query phrasings against Google News and dedupe by URL.

    Strategy: one query for the joined high-precision phrase, plus separate
    queries for each multi-word entity (Lakers vs Nuggets → "Lakers Nuggets",
    "Lakers injury report", "Nuggets injury report"). This catches articles
    that wouldn't surface on a single phrasing.
    """
    if not terms:
        return []
    queries: list[str] = []
    multi = [t for t in terms if " " in t][:2]
    single = [t for t in terms if " " not in t and len(t) >= 5][:3]
    if single:
        queries.append(" ".join(single[:2]))
        for s in single[:2]:
            queries.append(f"{s} injury")
    for m in multi:
        queries.append(f'"{m}"')

    seen: set[str] = set()
    out: list[NewsDoc] = []
    for q in queries[:5]:
        for d in fetch_google_news(q, limit=per_query, when="1d"):
            if d.url and d.url in seen:
                continue
            if d.url:
                seen.add(d.url)
            out.append(d)
    return out


def fetch_espn_news(limit: int = 25) -> list[NewsDoc]:
    """ESPN's undocumented public JSON news endpoint. Cleaner than RSS — has
    structured headline/description/published fields and stable schema."""
    out: list[NewsDoc] = []
    for path in (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news",
        "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/news",
    ):
        try:
            with httpx.Client(timeout=8.0) as c:
                r = c.get(path)
                r.raise_for_status()
                data = r.json()
        except Exception:
            continue
        for art in (data.get("articles") or [])[:limit]:
            link = ""
            for L in (art.get("links") or {}).get("web", {}).values() if isinstance((art.get("links") or {}).get("web"), dict) else []:
                if isinstance(L, str):
                    link = L
                    break
            out.append(NewsDoc(
                url=link or "",
                title=art.get("headline", "") or "",
                body=art.get("description", "") or "",
                publish_date=art.get("published") or art.get("lastModified"),
                source="news:espn-api",
            ))
    return out


def fetch_article(url: str) -> NewsDoc:
    """Single-article fetch — wires through feedparser when given a feed link.

    For arbitrary article URLs the RSS summary in fetch_feed is usually enough;
    deep article extraction is a Phase 3 follow-up if we need full body text.
    """
    raise NotImplementedError("Use fetch_all_default() + match_terms() for v1")


_STOPWORDS = {
    "yes", "no", "the", "and", "for", "will", "win", "wins", "winner",
    "game", "match", "vs", "men", "women", "league", "season", "team",
    "tonight", "today", "open", "close", "over", "under", "year", "month",
    "june", "july", "may", "april", "march", "october", "fed", "btc", "eth",
    "america", "american", "united", "states", "world", "national",
}


def match_terms(docs: Iterable[NewsDoc], terms: list[str]) -> list[NewsDoc]:
    """Filter docs that strongly reference the market.

    Acceptance rule (in order of strength):
      1. ≥1 multi-word term match (e.g. "Anthony Davis", "Federal Reserve") — high precision
      2. ≥2 distinct single-word matches in the same doc (e.g. both "Lakers" and "Nuggets")
      3. ≥1 single-word match for a sufficiently long, specific term (≥7 chars)

    Single-word matches alone for short common nouns (e.g. only "Bitcoin" with no
    other context) are dropped — those let unrelated content through, which is
    the bug we're fixing.
    """
    if not terms:
        return []
    multi = [t.lower() for t in terms if " " in t]
    single = [
        t.lower() for t in terms
        if " " not in t and len(t) >= 5 and t.lower() not in _STOPWORDS
    ]
    long_single = [t for t in single if len(t) >= 7]
    out: list[NewsDoc] = []
    for d in docs:
        hay = f"{d.title} {d.body}".lower()
        m_hits = [n for n in multi if n in hay]
        s_hits = [n for n in single if n in hay]
        long_hits = [n for n in long_single if n in hay]
        if m_hits or len(s_hits) >= 2 or long_hits:
            d.matched_terms = m_hits + s_hits
            out.append(d)
    return out
