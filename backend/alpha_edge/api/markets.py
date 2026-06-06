from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Market, SentimentEvent, Signal
from alpha_edge.model.decision import make_decision
from alpha_edge.model.kelly import half_kelly_capped
from alpha_edge.model.player_prop import is_player_prop, parse_prop_question, project
from alpha_edge.model.predict import predict_market
from alpha_edge.schemas import MarketOut

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("", response_model=list[MarketOut])
def list_markets(
    limit: int = 100,
    offset: int = 0,
    include_closed: bool = False,
    db: Session = Depends(get_session),
) -> list[Market]:
    stmt = select(Market)
    if include_closed:
        # Full history (incl. resolved / past-close), most-recently-ingested first.
        stmt = stmt.order_by(Market.created_at.desc())
    else:
        # Only tradeable markets, soonest-to-close first (i.e. most current).
        stmt = stmt.where(Market.active_clause()).order_by(Market.close_time.asc())
    stmt = stmt.limit(limit).offset(offset)
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
    kelly = half_kelly_capped(pred.probability, market_price)
    decimal_odds = (1.0 / market_price) if market_price > 0 else None

    events = list(
        db.scalars(
            select(SentimentEvent)
            .where(SentimentEvent.market_id == market_id)
            .order_by(SentimentEvent.detected_at.desc())
            .limit(50)
        )
    )
    decision_result = make_decision(pred, market_price, events)

    # Player-prop projection (only populated when the market is a detected prop)
    prop_block: dict | None = None
    if is_player_prop(market.question_text):
        parse = parse_prop_question(market.question_text)
        proj = project(parse)
        if proj:
            prop_block = {
                "is_player_prop": True,
                "parsed": {
                    "player_name": parse.player_name,
                    "prop_type": parse.prop_type,
                    "line": parse.line,
                    "side": parse.side,
                },
                "base_projection": round(proj.base, 2),
                "projected_mean": round(proj.projected_mean, 2),
                "adjusted_sd": round(proj.adjusted_sd, 2),
                "z_score": round(proj.z_score, 3),
                "model_prob_over": round(proj.prob_over, 4),
                "model_prob_under": round(proj.prob_under, 4),
                "n_games_used": proj.n_games_used,
                "sd_source": proj.sd_source,
                "flags": proj.flags,
                "adjustments": [
                    {"name": a.name, "value": round(a.value, 2), "note": a.note}
                    for a in proj.adjustments
                ],
            }
        else:
            prop_block = {
                "is_player_prop": True,
                "parsed": {
                    "player_name": parse.player_name,
                    "prop_type": parse.prop_type,
                    "line": parse.line,
                    "side": parse.side,
                },
                "error": "No gamelog data — player not in BBRef slug map or gamelog empty.",
            }

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
            "b": round(kelly["b"], 3),
            "full_kelly_fraction": round(kelly["full_kelly"], 4),
            "half_kelly_fraction": round(kelly["half_kelly"], 4),
            "capped_fraction": round(kelly["capped"], 4),
            "capped_pct_bankroll": round(kelly["capped"] * 100, 2),
            "was_capped_at_3pct": kelly["was_capped"],
            "rule": "f* = (b·p − q) / b ; b = 1/price − 1 ; recommend ½·f* capped at 3% of bankroll",
        },
        "decision": {
            "decision": decision_result.decision,
            "risk_level": decision_result.risk_level,
            "confidence": decision_result.confidence,
            "confidence_floor": 7,
            "deductions": decision_result.confidence_breakdown.deductions,
            "bonuses": decision_result.confidence_breakdown.bonuses,
            "flags": decision_result.confidence_breakdown.flags,
            "reasoning": decision_result.reasoning,
            "outcome_forecast": decision_result.outcome_forecast,
            "outcome_forecast_pct": round(decision_result.outcome_forecast_pct, 4),
            "saturated_market": decision_result.saturated_market,
        },
        "player_prop": prop_block,
        "math_note": (
            "posterior_log_odds = log_odds(market_price) + Σ_source clip(Σ β·x, ±0.8). "
            "x = polarity × relevance × confidence. β is per-source predictive coefficient. "
            "ci_95 = sigmoid(post ± 1.96·σ); Var(σ²) = Σ per-evidence variance. "
            "Decision: BET if |edge| ≥ 5pp AND confidence ≥ 7; else NO_BET."
        ),
    }

