"""Reddit ingestion.

Default path: Reddit's public per-subreddit RSS feeds (no auth, no app, no
Responsible Builder Policy review). Each subreddit has a stable .rss endpoint
that returns the latest posts as Atom XML.

Upgrade path: PRAW (the official Reddit API) activates when REDDIT_CLIENT_ID
and REDDIT_CLIENT_SECRET are set. PRAW gives access to comments, search, and
deep history that RSS doesn't expose. Optional.
"""
from __future__ import annotations

import re
import socket
from collections.abc import Iterable
from dataclasses import dataclass, field

import feedparser

from alpha_edge.config import get_settings

socket.setdefaulttimeout(8.0)

DEFAULT_SUBREDDITS: list[str] = ["nba", "sportsbook", "nfl", "soccer", "kalshimarkets"]


@dataclass
class RedditDoc:
    subreddit: str
    author: str
    title: str
    body: str
    permalink: str
    created_utc: float
    matched_terms: list[str] = field(default_factory=list)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def is_configured() -> bool:
    """Always True now — public RSS needs no credentials.

    Returns True even when PRAW credentials are missing, because the RSS path
    still works. Pipeline summary uses this to surface 'reddit_enabled'.
    """
    return True


def _has_praw() -> bool:
    s = get_settings()
    return bool(s.reddit_client_id and s.reddit_client_secret)


def _fetch_via_rss(subreddit: str, limit: int) -> list[RedditDoc]:
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss?limit={min(100, limit)}"
    parsed = feedparser.parse(
        url,
        request_headers={"User-Agent": get_settings().reddit_user_agent},
    )
    out: list[RedditDoc] = []
    for entry in parsed.entries:
        author = ""
        if entry.get("authors"):
            author = entry["authors"][0].get("name", "")
        elif entry.get("author"):
            author = entry["author"]
        out.append(
            RedditDoc(
                subreddit=subreddit,
                author=author or "unknown",
                title=_strip_html(entry.get("title", "")),
                body=_strip_html(entry.get("summary", "") or entry.get("description", "")),
                permalink=entry.get("link", ""),
                created_utc=0.0,
            )
        )
    return out


def _fetch_via_praw(subreddit: str, limit: int) -> list[RedditDoc]:
    s = get_settings()
    import praw

    client = praw.Reddit(
        client_id=s.reddit_client_id,
        client_secret=s.reddit_client_secret,
        user_agent=s.reddit_user_agent,
        check_for_async=False,
    )
    out: list[RedditDoc] = []
    for post in client.subreddit(subreddit).new(limit=limit):
        out.append(
            RedditDoc(
                subreddit=subreddit,
                author=str(post.author or "unknown"),
                title=post.title or "",
                body=(post.selftext or "")[:2000],
                permalink=f"https://reddit.com{post.permalink}",
                created_utc=float(post.created_utc),
            )
        )
    return out


def stream_subreddit(name: str, limit: int = 50) -> Iterable[RedditDoc]:
    if _has_praw():
        try:
            return iter(_fetch_via_praw(name, limit))
        except Exception:
            pass  # fall through to RSS
    try:
        return iter(_fetch_via_rss(name, limit))
    except Exception:
        return iter(())


def fetch_default(limit_per_sub: int = 50) -> list[RedditDoc]:
    out: list[RedditDoc] = []
    for sub in DEFAULT_SUBREDDITS:
        try:
            out.extend(list(stream_subreddit(sub, limit=limit_per_sub)))
        except Exception:
            continue
    return out


_STOPWORDS = {
    "yes", "no", "the", "and", "for", "will", "win", "wins", "winner",
    "game", "match", "vs", "men", "women", "league", "season", "team",
    "tonight", "today", "open", "close", "over", "under", "year", "month",
    "june", "july", "may", "april", "march", "october", "fed", "btc", "eth",
    "america", "american", "united", "states", "world", "national",
}


def match_terms(docs: Iterable[RedditDoc], terms: list[str]) -> list[RedditDoc]:
    multi = [t.lower() for t in terms if " " in t]
    single = [
        t.lower() for t in terms
        if " " not in t and len(t) >= 5 and t.lower() not in _STOPWORDS
    ]
    if not (multi or single):
        return []
    out: list[RedditDoc] = []
    for d in docs:
        hay = f"{d.title} {d.body}".lower()
        m_hits = [n for n in multi if n in hay]
        s_hits = [n for n in single if n in hay]
        if m_hits or s_hits:
            d.matched_terms = m_hits + s_hits
            out.append(d)
    return out
