"""Admin endpoints — manual pipeline triggers + diagnostics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Market, Outcome, Signal
from alpha_edge.workers.tasks import refresh_all, refresh_priority

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/refresh")
def refresh(polymarket_limit: int = 30, kalshi_limit: int = 30) -> dict:
    """Run the full ingest → sentiment → signal pipeline once. Returns a summary."""
    summary = refresh_all(
        polymarket_limit=polymarket_limit,
        kalshi_limit=kalshi_limit,
    )
    return summary.to_dict()


@router.post("/refresh-priority")
def refresh_priority_endpoint(
    polymarket_limit: int = 12,
    kalshi_limit: int = 20,
    min_liquidity: float = 1000.0,
) -> dict:
    """Sub-30s refresh of liquid sports markets only."""
    summary = refresh_priority(
        polymarket_limit=polymarket_limit,
        kalshi_limit=kalshi_limit,
        min_liquidity=min_liquidity,
    )
    return summary.to_dict()


@router.get("/closing-line-tracking")
def closing_line_tracking(db: Session = Depends(get_session)) -> dict:
    """Edge-persistence metric: for resolved markets, did our model_p predict
    the direction the market price moved between first and last signal?

    A correctly-calibrated model with edge should see closing market prices
    move toward our model_p before resolution. We compute:
      - n: count of resolved markets with ≥2 signals
      - hit_rate: fraction where market moved toward our edge direction
      - avg_market_move: mean of (last_market_price - first_market_price) signed
        in the direction of our initial edge
      - resolution_accuracy: fraction where the YES/NO outcome matched the
        side our initial signal favored (model_p > 0.5 → YES)
    """
    stmt = (
        select(Market, Signal)
        .join(Signal, Signal.market_id == Market.id)
        .where(Market.outcome.is_not(None))
        .order_by(Signal.market_id, Signal.generated_at)
    )
    rows = list(db.execute(stmt).all())
    by_market: dict = {}
    for market, signal in rows:
        by_market.setdefault(market.id, {"market": market, "signals": []})
        by_market[market.id]["signals"].append(signal)

    n = 0
    direction_hits = 0
    move_signed_total = 0.0
    resolution_correct = 0
    samples: list[dict] = []
    for entry in by_market.values():
        signals = entry["signals"]
        if len(signals) < 2:
            continue
        market = entry["market"]
        first, last = signals[0], signals[-1]
        initial_edge = first.model_probability - first.market_price
        if abs(initial_edge) < 0.01:
            continue
        n += 1
        market_move = last.market_price - first.market_price
        # Signed in direction of our edge
        signed_move = market_move if initial_edge >= 0 else -market_move
        move_signed_total += signed_move
        if signed_move > 0:
            direction_hits += 1
        outcome_yes = 1 if market.outcome == Outcome.YES else 0
        if (initial_edge > 0 and outcome_yes == 1) or (initial_edge < 0 and outcome_yes == 0):
            resolution_correct += 1
        if len(samples) < 25:
            samples.append({
                "market_id": str(market.id),
                "question_text": market.question_text[:120],
                "initial_model_p": round(first.model_probability, 3),
                "initial_market_p": round(first.market_price, 3),
                "final_market_p": round(last.market_price, 3),
                "initial_edge": round(initial_edge, 3),
                "market_moved_toward_edge": round(signed_move, 3),
                "outcome": market.outcome.value if market.outcome else None,
            })

    return {
        "resolved_markets_with_signals": n,
        "direction_hit_rate": round(direction_hits / n, 3) if n else None,
        "avg_market_move_toward_edge": round(move_signed_total / n, 4) if n else None,
        "resolution_accuracy": round(resolution_correct / n, 3) if n else None,
        "samples": samples,
    }
