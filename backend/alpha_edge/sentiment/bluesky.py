"""Bluesky public search — no auth, no API key.

Uses api.bsky.app's app.bsky.feed.searchPosts XRPC endpoint, which is publicly
readable. Bluesky has growing presence among sports media, journalists, and
beat reporters who left Twitter.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx

API_BASE = "https://api.bsky.app/xrpc"


@dataclass
class BlueskyDoc:
    handle: str
    text: str
    url: str
    created_at: str
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    matched_terms: list[str] = field(default_factory=list)


def search_posts(query: str, limit: int = 25) -> Iterable[BlueskyDoc]:
    if not query:
        return iter(())
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(
                f"{API_BASE}/app.bsky.feed.searchPosts",
                params={"q": query, "limit": min(100, limit)},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return iter(())
    out: list[BlueskyDoc] = []
    for p in data.get("posts", []):
        rec = p.get("record") or {}
        author = p.get("author") or {}
        handle = author.get("handle") or ""
        rkey = (p.get("uri") or "").split("/")[-1]
        out.append(
            BlueskyDoc(
                handle=handle,
                text=(rec.get("text") or "")[:500],
                url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                created_at=rec.get("createdAt") or "",
                like_count=int(p.get("likeCount") or 0),
                reply_count=int(p.get("replyCount") or 0),
                repost_count=int(p.get("repostCount") or 0),
                matched_terms=[query],
            )
        )
    return iter(out)


def credibility_for_post(doc: BlueskyDoc) -> float:
    """Rough heuristic: engagement-weighted credibility, capped.

    A post with 100+ likes from a verified-ish handle gets weighted closer to
    Twitter-tier credibility. Most posts default to 0.4 (matches reddit:nba).
    """
    base = 0.4
    if doc.like_count >= 50:
        base += 0.1
    if doc.like_count >= 200:
        base += 0.1
    if doc.repost_count >= 25:
        base += 0.1
    return min(0.85, base)
