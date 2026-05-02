"""Reddit scraping for r/nba, r/sportsbook, r/KalshiMarkets."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class RedditDoc:
    subreddit: str
    author: str
    title: str
    body: str
    permalink: str
    created_utc: float


def stream_subreddit(name: str, limit: int = 100) -> Iterable[RedditDoc]:
    raise NotImplementedError("Wire to PRAW in Phase 3")
