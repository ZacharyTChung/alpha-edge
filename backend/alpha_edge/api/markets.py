from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Market, Signal
from alpha_edge.model.predict import kelly_fraction_quarter, predict_market
from alpha_edge.schemas import MarketOut

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("", response_model=list[MarketOut])
def list_markets(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_session),
) -> list[Market]:
    stmt = select(Market).order_by(Market.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{market_id}", response_model=MarketOut)
def get_market(market_id: UUID, db: Session = Depends(get_session)) -> Market:
    market = db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.get("/{market_id}/calculation")
def get_calculation(market_id: UUID, db: Session = Depends(get_session)) -> dict:
    """Full numerical breakdown of the model's posterior for one market.

    Returns every input, intermediate value, and coefficient that goes into
    the Bayesian update. Powers the "Calculation" panel in the UI.
    """
    market = db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    latest = db.scalar(
        select(Signal)
        .where(Signal.market_id == market_id)
        .order_by(Signal.generated_at.desc())
        .limit(1)
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="No signal for this market yet")

    market_price = float(latest.market_price)
    pred = predict_market(db, market, market_price)

    edge = pred.probability - market_price
    kelly = kelly_fraction_quarter(pred.probability, market_price)
    decimal_odds = (1.0 / market_price) if market_price > 0 else None

    return {
        "market": {
            "question_text": market.question_text,
            "platform": market.platform.value,
            "category": market.category.value,
            "market_price_yes": round(market_price, 4),
            "decimal_odds_yes": round(decimal_odds, 3) if decimal_odds else None,
            "implied_payout_per_dollar": round(decimal_odds - 1, 3) if decimal_odds else None,
        },
        "prior": {
            "p_market": round(market_price, 4),
            "log_odds": round(pred.prior_log_odds, 4),
            "comment": "Market price treated as prior; Phase 2 will swap in a stats-based prior",
        },
        "evidence": {
            "n_events": pred.n_evidence,
            "delta_log_odds": round(pred.delta_log_odds, 4),
            "per_source": [
                {
                    "source_key": c.source_key,
                    "n_events": c.n_events,
                    "beta_coefficient": round(c.beta, 3),
                    "avg_signed_score": round(c.avg_signed_score, 3),
                    "raw_log_LR": round(c.raw_logLR, 4),
                    "capped_log_LR": round(c.capped_logLR, 4),
                    "was_capped": abs(c.raw_logLR - c.capped_logLR) > 1e-6,
                    "variance_contribution": round(c.variance, 4),
                }
                for c in pred.contributions
            ],
        },
        "posterior": {
            "log_odds": round(pred.posterior_log_odds, 4),
            "probability": round(pred.probability, 4),
            "variance_log_odds": round(pred.variance_log_odds, 4),
            "sigma_log_odds": round(pred.sigma_log_odds, 4),
            "ci_95_low": round(pred.ci_low, 4),
            "ci_95_high": round(pred.ci_high, 4),
        },
        "edge": {
            "edge": round(edge, 4),
            "edge_pp": round(edge * 100, 2),
            "tier": latest.signal_tier.value,
        },
        "betting": {
            "decimal_odds_yes": round(decimal_odds, 3) if decimal_odds else None,
            "full_kelly_fraction": round(kelly * 4, 4) if kelly > 0 else 0.0,
            "quarter_kelly_fraction": round(kelly, 4),
            "quarter_kelly_pct_bankroll": round(kelly * 100, 2),
            "rule": "f* = (b·p − q) / b ; b = 1/price − 1 ; recommend ¼·f*",
        },
        "math_note": (
            "posterior_log_odds = log_odds(market_price) + Σ_source clip(Σ β·x, ±0.8). "
            "x = polarity × relevance × confidence. β is per-source predictive coefficient. "
            "ci_95 = sigmoid(post ± 1.96·σ); Var(σ²) = Σ per-evidence variance."
        ),
    }

