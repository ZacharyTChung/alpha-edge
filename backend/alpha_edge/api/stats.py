"""Dashboard stats — counts and aggregates for the frontend overview."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Market, SentimentEvent, Signal, SignalTier

router = APIRouter(tags=["stats"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_session)) -> dict:
    """One-shot counts powering the dashboard banner."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    market_count = db.scalar(select(func.count(Market.id))) or 0
    open_market_count = db.scalar(
        select(func.count(Market.id)).where(Market.resolved_at.is_(None))
    ) or 0
    signal_count = db.scalar(select(func.count(Signal.id))) or 0
    sentiment_count = db.scalar(select(func.count(SentimentEvent.id))) or 0
    recent_sentiment = db.scalar(
        select(func.count(SentimentEvent.id)).where(SentimentEvent.detected_at >= cutoff)
    ) or 0
    last_signal_at = db.scalar(select(func.max(Signal.generated_at)))

    # Latest signal per market, then count by tier
    latest_subq = (
        select(Signal.market_id, func.max(Signal.generated_at).label("ts"))
        .group_by(Signal.market_id)
        .subquery()
    )
    latest_signals_stmt = (
        select(Signal.signal_tier, func.count(Signal.id))
        .join(latest_subq, (Signal.market_id == latest_subq.c.market_id) & (Signal.generated_at == latest_subq.c.ts))
        .group_by(Signal.signal_tier)
    )
    by_tier = {tier.value: 0 for tier in SignalTier}
    for tier, n in db.execute(latest_signals_stmt).all():
        by_tier[tier.value] = int(n)

    return {
        "market_count": int(market_count),
        "open_market_count": int(open_market_count),
        "signal_count": int(signal_count),
        "sentiment_count": int(sentiment_count),
        "sentiment_last_24h": int(recent_sentiment),
        "last_signal_at": last_signal_at.isoformat() if last_signal_at else None,
        "by_tier": by_tier,
    }
