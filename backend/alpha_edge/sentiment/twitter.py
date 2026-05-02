"""Twitter/X via tweepy v2 search.

Activates when TWITTER_BEARER_TOKEN is set. Without it the helpers return empty.
Free tier of the X API is heavily rate-limited (~100 reads/month at time of
writing), so this layer is mostly for users on paid Basic+ tiers.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from alpha_edge.config import get_settings


@dataclass
class TwitterDoc:
    author: str
    text: str
    url: str
    created_at: str
    matched_terms: list[str] = field(default_factory=list)


def _client():
    token = get_settings().twitter_bearer_token
    if not token:
        return None
    import tweepy

    return tweepy.Client(bearer_token=token, wait_on_rate_limit=False)


def is_configured() -> bool:
    return bool(get_settings().twitter_bearer_token)


def search_recent(query: str, max_results: int = 25) -> Iterable[TwitterDoc]:
    client = _client()
    if client is None:
        return iter(())
    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=min(100, max_results),
            tweet_fields=["created_at", "author_id", "text"],
            expansions=["author_id"],
        )
    except Exception:
        return iter(())
    if not resp or not resp.data:
        return iter(())
    users = {u.id: u.username for u in (resp.includes.get("users") or [])} if resp.includes else {}
    out: list[TwitterDoc] = []
    for t in resp.data:
        user = users.get(t.author_id, str(t.author_id))
        out.append(
            TwitterDoc(
                author=user,
                text=t.text,
                url=f"https://x.com/{user}/status/{t.id}",
                created_at=str(t.created_at) if t.created_at else "",
            )
        )
    return iter(out)
