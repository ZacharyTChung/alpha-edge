"""Polymarket Gamma Markets API client.

Public read API; no auth required for the listing endpoint we use.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_edge.config import get_settings
from alpha_edge.db.models import Category, Market, Platform


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    base = get_settings().polymarket_api_base
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base}{path}", params=params or {})
        response.raise_for_status()
        return response.json()


def fetch_active_markets(
    limit: int = 100,
    tag_slug: str | None = None,
    min_volume: float = 0.0,
) -> list[dict]:
    """Return open, active Polymarket binary markets, ordered by volume desc."""
    params: dict[str, Any] = {
        "closed": "false",
        "active": "true",
        "limit": limit,
        "order": "volume",
        "ascending": "false",
    }
    if tag_slug:
        params["tag_slug"] = tag_slug
    raw = _get("/markets", params)
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for m in raw:
        try:
            outcomes = m.get("outcomes")
            prices = m.get("outcomePrices")
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)
            if not outcomes or not prices or len(prices) < 2:
                continue
            yes_price = float(prices[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        try:
            volume = float(m.get("volume") or 0.0)
        except (TypeError, ValueError):
            volume = 0.0
        if volume < min_volume:
            continue
        out.append({
            "external_id": f"poly:{m.get('id')}",
            "question_text": m.get("question") or "",
            "end_date": m.get("endDate"),
            "yes_price": yes_price,
            "volume": volume,
            "liquidity": float(m.get("liquidity") or 0.0),
            "raw": m,
        })
    return out


def list_open_markets(category: str | None = None) -> Iterable[dict]:
    return fetch_active_markets(tag_slug=category)


def get_market(condition_id: str) -> dict:
    return _get(f"/markets/{condition_id}")


_SPORTS_TAGS = ("sports", "nba", "nfl", "mlb", "nhl", "soccer")
_FINANCE_TAGS = ("crypto", "finance", "stocks", "economy")
_POLITICS_TAGS = ("politics", "trump", "election")


def _classify_category(raw: dict) -> Category:
    blob = json.dumps(raw).lower()
    if any(t in blob for t in _SPORTS_TAGS):
        return Category.SPORTS
    if any(t in blob for t in _FINANCE_TAGS):
        return Category.FINANCE
    if any(t in blob for t in _POLITICS_TAGS):
        return Category.POLITICS
    return Category.SPORTS


def to_market_row(item: dict) -> Market:
    """Build a (transient) Market ORM row from an ingest dict."""
    end_iso = item.get("end_date") or "2099-01-01T00:00:00Z"
    close_time = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    # Polymarket reports volume in USD lifetime; treat as liquidity proxy.
    liquidity = float(item.get("volume") or 0.0)
    return Market(
        platform=Platform.POLYMARKET,
        external_id=item["external_id"],
        question_text=item["question_text"][:500],
        category=_classify_category(item.get("raw") or {}),
        resolution_criteria=(item.get("raw") or {}).get("description", "") or "",
        close_time=close_time,
        liquidity=liquidity,
    )
