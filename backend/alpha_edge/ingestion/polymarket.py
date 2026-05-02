"""Polymarket Gamma Markets API client."""
from __future__ import annotations

from collections.abc import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_edge.config import get_settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(path: str, params: dict | None = None) -> dict | list:
    base = get_settings().polymarket_api_base
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base}{path}", params=params or {})
        response.raise_for_status()
        return response.json()


def list_open_markets(category: str | None = None) -> Iterable[dict]:
    raise NotImplementedError("Wire to /markets endpoint in Phase 1")


def get_market(condition_id: str) -> dict:
    raise NotImplementedError("Wire to /markets/{condition_id}")
