"""Kalshi REST API client — market polling and resolution data."""
from __future__ import annotations

from collections.abc import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_edge.config import get_settings

KALSHI_BASE = "https://trading-api.kalshi.com/trade-api/v2"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(path: str, params: dict | None = None) -> dict:
    settings = get_settings()
    headers = {}
    if settings.kalshi_api_key:
        headers["Authorization"] = f"Bearer {settings.kalshi_api_key}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{KALSHI_BASE}{path}", params=params or {}, headers=headers)
        response.raise_for_status()
        return response.json()


def list_open_markets(category: str | None = None) -> Iterable[dict]:
    raise NotImplementedError("Wire to /markets endpoint in Phase 1")


def get_market_orderbook(ticker: str) -> dict:
    raise NotImplementedError("Wire to /markets/{ticker}/orderbook")


def get_market_history(ticker: str) -> Iterable[dict]:
    raise NotImplementedError("Wire to /markets/{ticker}/history for resolution data")
