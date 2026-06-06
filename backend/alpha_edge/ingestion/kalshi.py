"""Kalshi REST API client — public read endpoints, no auth required for listings.

The trade-api/v2 endpoints under api.elections.kalshi.com expose open markets and
last-traded prices without authentication. Trading actions (orders, balances)
would require RSA-signed requests; we don't do that here.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_edge.db.models import Category, Market, Platform

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(path: str, params: dict[str, Any] | None = None) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{KALSHI_BASE}{path}", params=params or {})
        response.raise_for_status()
        return response.json()


_SINGLE_EVENT_SERIES = ("KXNBAGAME", "KXNFLGAME", "KXMLBGAME", "KXNHLGAME")

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
# Game tickers embed the event date: KXNBAGAME-26JUN03NYKSAS-NYK (date only) or
# KXMLBGAME-26MAY092110ATLLAD-ATL (date + HHMM start time).
_GAME_TICKER = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})(\d{4})?")


def _ticker_close(ticker: str) -> datetime | None:
    """Derive the market's real close time from a Kalshi game ticker.

    Kalshi's API ``close_time`` for these markets is the *series* window end
    (a Finals market shows 2026-06-18 for a June 3 game), so we prefer the date
    embedded in the ticker. A buffer is added so a game played *today* isn't
    hidden before tip-off: ~4h past the start when the ticker carries a time
    (MLB/NHL), else the end of the game day (date-only NBA/NFL).
    """
    m = _GAME_TICKER.search(ticker or "")
    if not m:
        return None
    yy, mon, dd, hhmm = m.groups()
    month = _MONTHS.get(mon)
    if month is None:
        return None
    try:
        base = datetime(2000 + int(yy), month, int(dd), tzinfo=timezone.utc)
        if hhmm:
            base = base.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]))
            return base + timedelta(hours=4)
        return base + timedelta(days=1)
    except ValueError:
        return None


def _event_key(ticker: str) -> str:
    """Collapse a per-team game ticker to its base event.

    Kalshi lists one market per outcome: KXNBAGAME-26JUN03NYKSAS-NYK and
    ...-SAS are the two sides of one binary market, sharing the base event
    KXNBAGAME-26JUN03NYKSAS. We keep one row per event to avoid duplicates.
    """
    return ticker.rsplit("-", 1)[0] if ticker and "-" in ticker else ticker


def _ticker_of(it: dict) -> str:
    return it.get("ticker") or it.get("external_id") or ""


def _dedupe_by_event(items: list[dict]) -> list[dict]:
    """Keep one market per event, deterministically the lexicographically-smallest
    team-side ticker. Determinism matters: ingestion must always pick the SAME
    side so re-ingestion upserts the same row instead of creating the other side.
    """
    best: dict[str, dict] = {}
    order: list[str] = []
    for it in items:
        key = _event_key(_ticker_of(it))
        if key not in best:
            best[key] = it
            order.append(key)
        elif _ticker_of(it) < _ticker_of(best[key]):
            best[key] = it
    return [best[key] for key in order]


def fetch_active_markets(
    limit: int = 200,
    series_ticker: str | None = None,
) -> list[dict]:
    """Return open Kalshi markets with a usable yes price.

    Single-page fetch (no pagination): the unauth read tier rate-limits hard.
    The default `/markets?status=open` page is dominated by multi-event parlays
    we don't want. We fan out across known single-event series so the result is
    a clean list of bettable game/match markets.
    """
    series_to_try: list[str | None]
    if series_ticker is not None:
        series_to_try = [series_ticker]
    else:
        series_to_try = list(_SINGLE_EVENT_SERIES)

    out: list[dict] = []
    for series in series_to_try:
        if len(out) >= limit:
            break
        params: dict[str, Any] = {"status": "open", "limit": min(200, limit - len(out))}
        if series:
            params["series_ticker"] = series
        try:
            data = _get("/markets", params)
        except Exception:
            continue
        markets = data.get("markets") or []
        out.extend(_normalize(markets, limit - len(out)))
    return _dedupe_by_event(out)


def _normalize(markets: list[dict], remaining: int) -> list[dict]:
    out: list[dict] = []
    for m in markets:
        if len(out) >= remaining:
            break
        yes_price = _yes_price(m)
        if yes_price is None:
            continue
        ticker = m.get("ticker") or ""
        if "MVE" in ticker or "MULTIGAME" in ticker:
            continue
        title = m.get("title") or m.get("subtitle") or ""
        if title.count(",") >= 3:
            continue
        out.append({
            "external_id": f"kalshi:{m.get('ticker')}",
            "question_text": (m.get("title") or m.get("subtitle") or m.get("ticker") or "")[:500],
            "end_date": m.get("close_time") or m.get("expiration_time"),
            "yes_price": yes_price,
            "ticker": m.get("ticker"),
            "raw": m,
        })
    return out


def _yes_price(m: dict) -> float | None:
    for k in ("yes_bid_dollars", "yes_ask_dollars", "last_price_dollars"):
        v = m.get(k)
        if v in (None, "", "0", "0.0", "0.0000"):
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if 0.0 < f < 1.0:
            return f
    return None


def list_open_markets(category: str | None = None) -> Iterable[dict]:
    series = None
    if category and category.lower() == "nba":
        series = "KXNBAGAME"
    return fetch_active_markets(series_ticker=series)


def get_market_orderbook(ticker: str) -> dict:
    return _get(f"/markets/{ticker}/orderbook")


def get_market_history(ticker: str) -> Iterable[dict]:
    return _get(f"/markets/{ticker}/history").get("history", [])


def _classify_category(ticker: str) -> Category:
    t = (ticker or "").upper()
    if "NBA" in t or "MLB" in t or "NFL" in t or "NHL" in t or "MMA" in t or "BOX" in t or "GAME" in t:
        return Category.SPORTS
    if "BTC" in t or "ETH" in t or "FED" in t or "CPI" in t or "MARKET" in t:
        return Category.FINANCE
    return Category.POLITICS


def to_market_row(item: dict) -> Market:
    ticker = item.get("ticker") or ""
    # Prefer the real event date encoded in the ticker over Kalshi's series-window
    # close_time; fall back to the API field for any non-game ticker.
    close_time = _ticker_close(ticker)
    if close_time is None:
        end_iso = item.get("end_date") or "2099-01-01T00:00:00Z"
        close_time = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    raw = item.get("raw") or {}
    liquidity = 0.0
    for key in ("liquidity_dollars", "open_interest_fp", "notional_value_dollars"):
        try:
            v = float(raw.get(key) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            liquidity = v
            break
    return Market(
        platform=Platform.KALSHI,
        external_id=item["external_id"],
        question_text=item["question_text"][:500],
        category=_classify_category(item.get("ticker") or ""),
        resolution_criteria=raw.get("rules_primary", "") or "",
        close_time=close_time,
        liquidity=liquidity,
    )
