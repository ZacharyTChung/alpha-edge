"""Twitter/X scraping with entity + sentiment classification."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class TwitterDoc:
    author: str
    text: str
    url: str
    created_at: str


def search_recent(query: str, since_id: str | None = None) -> Iterable[TwitterDoc]:
    raise NotImplementedError("Wire to Tweepy v2 search_recent_tweets in Phase 3")
