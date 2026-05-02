"""News article ingestion via newspaper3k + spaCy NER."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class NewsDoc:
    url: str
    title: str
    body: str
    publish_date: str | None
    source: str


def fetch_article(url: str) -> NewsDoc:
    raise NotImplementedError("Wire to newspaper3k Article in Phase 3")


def fetch_feed(feed_url: str) -> Iterable[NewsDoc]:
    raise NotImplementedError("Wire to feedparser + newspaper3k pipeline in Phase 3")
