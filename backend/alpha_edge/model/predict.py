"""Bayesian fusion: combine the market-implied prior with weighted sentiment.

Math:
    posterior_log_odds = log_odds(prior) + k * Σ(score_i · credibility_i · novelty_i)
                                          / max(1, Σ credibility_i · novelty_i)
    edge = posterior - prior
where k controls how aggressively sentiment can move the posterior. We default
to 0.6: a fully-positive corpus of credibility-1.0 sources shifts log-odds by
+0.6 (≈ +0.15 prob at p=0.5).

CI: bootstrapped from sentiment dispersion, with a floor that widens when there
is little evidence. This is heuristic — replace with a real posterior from
Monte Carlo over component distributions when Phase 2 stats lands.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db.models import (
    Market,
    SentimentEvent,
    Signal,
)
from alpha_edge.market.edge import classify_tier
from alpha_edge.model.bayesian import from_log_odds, log_odds

K_SENTIMENT = 0.6
DEFAULT_CI_HALFWIDTH = 0.10


@dataclass
class Prediction:
    probability: float
    ci_low: float
    ci_high: float
    sentiment_score: float
    sentiment_weight: float
    stats_weight: float
    n_evidence: int


def predict_market(
    db: Session,
    market: Market,
    market_price: float,
) -> Prediction:
    """Return a Bayesian posterior given the latest sentiment events for `market`.

    Falls back to the market_price prior with a wide CI when there's no
    sentiment evidence yet.
    """
    if not 0.0 < market_price < 1.0:
        market_price = max(0.01, min(0.99, market_price))

    events = list(
        db.scalars(
            select(SentimentEvent)
            .where(SentimentEvent.market_id == market.id)
            .order_by(SentimentEvent.detected_at.desc())
            .limit(200)
        )
    )

    if not events:
        return Prediction(
            probability=market_price,
            ci_low=max(0.0, market_price - DEFAULT_CI_HALFWIDTH),
            ci_high=min(1.0, market_price + DEFAULT_CI_HALFWIDTH),
            sentiment_score=0.0,
            sentiment_weight=0.0,
            stats_weight=1.0,
            n_evidence=0,
        )

    weighted_sum = 0.0
    weight_total = 0.0
    raw_scores: list[float] = []
    for ev in events:
        w = float(ev.credibility_weight) * float(ev.novelty_score)
        score = _label_to_score(ev.sentiment.value)
        weighted_sum += w * score
        weight_total += w
        raw_scores.append(score)
    aggregate = weighted_sum / max(weight_total, 1e-6)

    posterior_lo = log_odds(market_price) + K_SENTIMENT * aggregate
    posterior = from_log_odds(posterior_lo)

    n = len(events)
    spread = statistics.stdev(raw_scores) if n > 1 else 0.5
    half = max(0.03, DEFAULT_CI_HALFWIDTH * spread / math.sqrt(n))
    sentiment_weight = min(0.6, 0.1 + 0.05 * n)

    return Prediction(
        probability=posterior,
        ci_low=max(0.0, posterior - half),
        ci_high=min(1.0, posterior + half),
        sentiment_score=aggregate,
        sentiment_weight=sentiment_weight,
        stats_weight=1.0 - sentiment_weight,
        n_evidence=n,
    )


def _label_to_score(label: str) -> float:
    return {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(label, 0.0)


def write_signal(
    db: Session,
    market: Market,
    market_price: float,
    prediction: Prediction,
) -> Signal:
    edge = prediction.probability - market_price
    sig = Signal(
        market_id=market.id,
        model_probability=prediction.probability,
        confidence_interval_low=prediction.ci_low,
        confidence_interval_high=prediction.ci_high,
        market_price=market_price,
        edge=edge,
        signal_tier=classify_tier(edge),
        sentiment_score=prediction.sentiment_score,
        sentiment_weight=prediction.sentiment_weight,
        stats_weight=prediction.stats_weight,
    )
    db.add(sig)
    return sig


def predict_market_id(db: Session, market_id: UUID, market_price: float) -> Prediction:
    market = db.get(Market, market_id)
    if market is None:
        raise ValueError(f"market {market_id} not found")
    return predict_market(db, market, market_price)
