"""Edge scoring and signal tier classification.

PRD section 5.4: edge = model_probability - market_price, adjusted for liquidity,
time to resolution, and model confidence.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db.models import Market, Signal, SignalTier
from alpha_edge.schemas import EdgeReportItem

STRONG_THRESHOLD = 0.10
LEAN_THRESHOLD = 0.04
FADE_THRESHOLD = -0.10


def classify_tier(edge: float) -> SignalTier:
    if edge >= STRONG_THRESHOLD:
        return SignalTier.STRONG
    if edge >= LEAN_THRESHOLD:
        return SignalTier.LEAN
    if edge <= FADE_THRESHOLD:
        return SignalTier.FADE
    return SignalTier.NONE


def current_edge_report(
    db: Session, min_edge: float = 0.05, limit: int = 50
) -> list[EdgeReportItem]:
    """Return latest signal per market with |edge| >= min_edge, sorted desc."""
    subq = (
        select(Signal.market_id, Signal.id)
        .order_by(Signal.market_id, Signal.generated_at.desc())
        .distinct(Signal.market_id)
        .subquery()
    )
    stmt = (
        select(Signal, Market)
        .join(subq, Signal.id == subq.c.id)
        .join(Market, Market.id == Signal.market_id)
        .where(Market.active_clause())
    )
    items: list[EdgeReportItem] = []
    for signal, market in db.execute(stmt).all():
        if abs(signal.edge) < min_edge:
            continue
        items.append(
            EdgeReportItem(
                market_id=market.id,
                question_text=market.question_text,
                model_probability=signal.model_probability,
                market_price=signal.market_price,
                edge=signal.edge,
                signal_tier=signal.signal_tier,
                platform=market.platform,
                category=market.category,
                liquidity=float(market.liquidity or 0.0),
            )
        )
    items.sort(key=lambda x: abs(x.edge), reverse=True)
    return items[:limit]
