"""Hacker News via Algolia search — no auth, no key.

Useful for finance and political markets: Fed announcements, regulatory news,
crypto / earnings stories all surface on HN early. Skip for sports markets.
"""
from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx


@dataclass
class HNDoc:
    title: str
    url: str
    points: int
    author: str
    created_at: str
    matched_terms: list[str] = field(default_factory=list)


def search_hn(query: str, hits: int = 10, days_back: int = 7) -> Iterable[HNDoc]:
    if not query:
        return iter(())
    cutoff = int(time.time()) - days_back * 86400
    params = {
        "query": query,
        "tags": "story",
        "hitsPerPage": min(50, hits),
        "numericFilters": f"created_at_i>{cutoff},points>5",
    }
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get("https://hn.algolia.com/api/v1/search", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return iter(())
    out: list[HNDoc] = []
    for h in data.get("hits", []):
        title = h.get("title") or h.get("story_title") or ""
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        out.append(
            HNDoc(
                title=title,
                url=url,
                points=int(h.get("points") or 0),
                author=h.get("author") or "",
                created_at=h.get("created_at") or "",
                matched_terms=[query],
            )
        )
    return iter(out)


def credibility_for_post(doc: HNDoc) -> float:
    """Heuristic: HN posts at ≥100 points generally have substance behind them."""
    base = 0.4
    if doc.points >= 50:
        base += 0.1
    if doc.points >= 200:
        base += 0.15
    if doc.points >= 500:
        base += 0.1
    return min(0.85, base)
