"""Admin endpoints — manual pipeline triggers + diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from alpha_edge.auth import require_admin_api_key
from alpha_edge.db import get_session
from alpha_edge.db.models import Market, Outcome, SentimentEvent, SentimentLabel, Signal
from alpha_edge.ingestion import basketball_ref as bbref_mod
from alpha_edge.market.edge import classify_tier
from alpha_edge.model import clv as clv_mod
from alpha_edge.model import elo_ratings
from alpha_edge.model.predict import predict_market
from alpha_edge.sentiment import llm as llm_mod
from alpha_edge.workers.tasks import refresh_all, refresh_priority

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)


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


@router.post("/reclassify-market/{market_id}")
def reclassify_market(market_id: UUID, db: Session = Depends(get_session)) -> dict:
    """Re-run Claude on every existing sentiment event for this market.

    Updates `sentiment`, `relevance_score`, `credibility_weight`, `llm_reasoning`
    in place. Drops events Claude judges off-topic (relevance < 0.2). Then
    regenerates the latest Signal so the model probability reflects the cleaned
    evidence.

    Use this on markets with mostly VADER-fallback events that don't actually
    align with the question — typically stale events ingested before the LLM
    layer was wired.
    """
    if not llm_mod.is_configured():
        raise HTTPException(
            status_code=400,
            detail="ANTHROPIC_API_KEY not set — reclassify needs the LLM",
        )

    market = db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    events = list(
        db.scalars(
            select(SentimentEvent).where(SentimentEvent.market_id == market_id)
        )
    )
    if not events:
        return {"reclassified": 0, "dropped": 0, "kept": 0}

    texts = [e.raw_text for e in events]
    sources = [
        f"{e.source.value}:{e.entity}" if e.entity else e.source.value for e in events
    ]
    stats_context = bbref_mod.market_stats_context(market.question_text)

    # Pass the platform/category as additional disambiguating context — without
    # this, "Chicago WS vs Los Angeles A" matches LA Lakers articles.
    contextual_question = (
        f"[{market.platform.value}/{market.category.value}] {market.question_text}"
    )

    # Batch in chunks of 12 — Claude truncates output silently when many texts
    # are passed at once, and returns 0 parseable classifications.
    BATCH = 12
    classifications: list = []
    for i in range(0, len(events), BATCH):
        chunk_texts = texts[i : i + BATCH]
        chunk_sources = sources[i : i + BATCH]
        chunk_classifications = llm_mod.classify_for_market(
            market_question=contextual_question,
            texts=chunk_texts,
            sources=chunk_sources,
            stats_context=stats_context,
        )
        if len(chunk_classifications) != len(chunk_texts):
            raise HTTPException(
                status_code=502,
                detail=(
                    f"LLM returned {len(chunk_classifications)} classifications "
                    f"for {len(chunk_texts)} texts in batch starting at index {i}"
                ),
            )
        classifications.extend(chunk_classifications)

    label_map = {
        "positive": SentimentLabel.POSITIVE,
        "negative": SentimentLabel.NEGATIVE,
        "neutral": SentimentLabel.NEUTRAL,
    }
    dropped_ids: list = []
    kept = 0
    for event, cls in zip(events, classifications, strict=True):
        if cls.relevance < 0.2:
            dropped_ids.append(event.id)
            continue
        event.sentiment = label_map.get(cls.sentiment, SentimentLabel.NEUTRAL)
        event.relevance_score = cls.relevance
        event.llm_reasoning = cls.reasoning
        # Scale current credibility by LLM confidence (don't double-shrink — clamp).
        scaled = event.credibility_weight * (0.5 + 0.5 * cls.confidence)
        event.credibility_weight = max(0.0, min(1.0, scaled))
        kept += 1

    if dropped_ids:
        db.execute(delete(SentimentEvent).where(SentimentEvent.id.in_(dropped_ids)))

    db.flush()

    # Pull the latest signal's market_price as the prior for the regenerated signal.
    latest_signal = db.scalar(
        select(Signal)
        .where(Signal.market_id == market_id)
        .order_by(Signal.generated_at.desc())
        .limit(1)
    )
    market_price = float(latest_signal.market_price) if latest_signal else 0.5

    pred = predict_market(db, market, market_price)
    edge = pred.probability - market_price
    new_signal = Signal(
        market_id=market.id,
        model_probability=pred.probability,
        confidence_interval_low=pred.ci_low,
        confidence_interval_high=pred.ci_high,
        market_price=market_price,
        edge=edge,
        signal_tier=classify_tier(edge),
        sentiment_score=pred.sentiment_score,
        sentiment_weight=pred.sentiment_weight,
        stats_weight=pred.stats_weight,
    )
    db.add(new_signal)
    db.commit()

    return {
        "reclassified": len(events),
        "kept": kept,
        "dropped": len(dropped_ids),
        "new_signal": {
            "model_probability": round(pred.probability, 3),
            "edge": round(edge, 3),
            "tier": classify_tier(edge).value,
        },
    }


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


@router.get("/clv-backtest")
def clv_backtest(min_edge: float = 0.03, db: Session = Depends(get_session)) -> dict:
    """Closing-line-value backtest, segmented by prior (Elo vs market).

    For every market that has CLOSED (or resolved) and has signal history, measure
    how far the market moved toward the model's side between its first actionable
    signal and the closing line. Positive mean CLV and a >50% beat-close rate are
    the signal that the model's edges are real, not noise — the standard test on
    near-efficient markets. Segmenting by Elo-prior vs market-prior answers the
    key question directly: does the Elo model actually beat the market?
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Market, Signal)
        .join(Signal, Signal.market_id == Market.id)
        .order_by(Signal.market_id, Signal.generated_at)
    )
    by_market: dict = {}
    for market, signal in db.execute(stmt).all():
        e = by_market.setdefault(market.id, {"market": market, "signals": []})
        e["signals"].append(signal)

    # bucket by status (closed = real CLV; open = line-movement-so-far) × prior.
    buckets: dict[str, list] = {f"{s}_{p}": [] for s in ("closed", "open") for p in ("elo", "market")}
    briers: dict[str, list] = {"closed_elo": [], "closed_market": []}
    samples: list[dict] = []
    for entry in by_market.values():
        market = entry["market"]
        signals = entry["signals"]
        result = clv_mod.clv_for_signals(signals, min_edge=min_edge)
        if result is None:
            continue
        is_closed = (market.close_time is not None and market.close_time < now) or market.outcome is not None
        status = "closed" if is_closed else "open"
        prior = "elo" if elo_ratings.prob_for_market(market) is not None else "market"
        buckets[f"{status}_{prior}"].append(result)
        if is_closed and market.outcome is not None:
            briers[f"closed_{prior}"].append(
                clv_mod.brier_score(signals[-1].model_probability, market.outcome == Outcome.YES)
            )
        if len(samples) < 25:
            samples.append({
                "question_text": market.question_text[:90],
                "status": status,
                "prior": prior,
                "side": "YES" if result.direction > 0 else "NO",
                "entry_market_p": round(result.entry_market_p, 3),
                "latest_market_p": round(result.close_market_p, 3),
                "clv_pp": result.clv_pp,
                "moved_toward_model": result.beat_close,
                "outcome": market.outcome.value if market.outcome else None,
            })

    def summarize(cs: list, bs: list | None = None) -> dict:
        if not cs:
            return {"n": 0, "beat_rate": None, "mean_clv_pp": None, "brier": None}
        return {
            "n": len(cs),
            "beat_rate": round(sum(1 for c in cs if c.beat_close) / len(cs), 3),
            "mean_clv_pp": round(sum(c.clv_pp for c in cs) / len(cs), 2),
            "brier": round(sum(bs) / len(bs), 4) if bs else None,
        }

    return {
        "min_edge": min_edge,
        "closed_backtest": {  # the real test: did we beat the closing line?
            "elo_prior": summarize(buckets["closed_elo"], briers["closed_elo"]),
            "market_prior": summarize(buckets["closed_market"], briers["closed_market"]),
        },
        "open_in_progress": {  # leading indicator: line movement toward us so far
            "elo_prior": summarize(buckets["open_elo"]),
            "market_prior": summarize(buckets["open_market"]),
        },
        "note": (
            "CLV = market move toward the model's side (entry→latest), in probability "
            "points. closed_backtest is the real test (>50% beat_rate + positive mean_clv_pp "
            "= real edge; brier on resolved only). open_in_progress is a leading indicator "
            "on live markets — not yet final CLV."
        ),
        "samples": samples,
    }
