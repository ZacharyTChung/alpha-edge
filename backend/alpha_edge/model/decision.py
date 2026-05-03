"""Decision logic per v2.0 spec.

- Confidence: starts at 8/10, subtract for risk flags, +1 if 3+ Tier 1-2 sources
  corroborate, floor of 3/10.
- Decision: BET OVER if edge ≥ +5pp AND confidence ≥ 7
            BET UNDER if edge ≤ −5pp AND confidence ≥ 7
            NO BET otherwise (low confidence or |edge| < 3pp = noise)
- Risk level: LOW / MEDIUM / HIGH from edge × confidence × signal-conflict count.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from alpha_edge.db.models import SentimentEvent
from alpha_edge.model.predict import Prediction
from alpha_edge.sentiment.credibility import beta_for

Decision = Literal["BET_OVER", "BET_UNDER", "NO_BET"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
OutcomeForecast = Literal["YES", "NO", "UNCERTAIN"]

# v2.0 thresholds
EDGE_NOISE_THRESHOLD = 0.03          # |edge| below 3pp = NO BET
EDGE_ACTIONABLE_THRESHOLD = 0.05     # need 5pp edge to recommend a bet
CONFIDENCE_BET_FLOOR = 7             # need confidence ≥ 7 to recommend
CONFIDENCE_FLOOR = 3                 # output never below this

# A market is "saturated" when its price has run so close to the bound that
# the available payout is too small to justify any risk, regardless of model
# disagreement. At p=0.99 a YES bet pays 1¢ on the dollar — not actionable.
SATURATED_HIGH = 0.95
SATURATED_LOW = 0.05


@dataclass
class ConfidenceBreakdown:
    score: int
    deductions: list[str] = field(default_factory=list)
    bonuses: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class DecisionResult:
    decision: Decision
    risk_level: RiskLevel
    edge: float
    confidence: int
    confidence_breakdown: ConfidenceBreakdown
    reasoning: str
    # Independent of the bet recommendation — what does the model think will
    # happen? Useful when the market is saturated and there's no betting edge
    # but the user still wants to know the predicted outcome.
    outcome_forecast: OutcomeForecast = "UNCERTAIN"
    outcome_forecast_pct: float = 0.5
    saturated_market: bool = False


def compute_confidence(
    events: list[SentimentEvent],
    prediction: Prediction,
    market_price: float,
) -> ConfidenceBreakdown:
    """v2.0 confidence: start at 8/10, subtract for flags."""
    score = 8
    deductions: list[str] = []
    bonuses: list[str] = []
    flags: dict[str, bool] = {
        "game_time_decision": False,
        "back_to_back": False,
        "small_sample": False,            # we don't track player game count yet
        "conflicting_signals": False,
        "high_variance": False,
        "line_moved_against": False,      # we don't yet diff first vs last signal
    }

    # Inspect events for flag triggers
    text_lower = " ".join((e.raw_text or "").lower() for e in events)
    if any(k in text_lower for k in ("game-time decision", "questionable", "being evaluated")):
        flags["game_time_decision"] = True
        score -= 2
        deductions.append("Game-time decision risk (-2)")
    if "back-to-back" in text_lower or "second night" in text_lower or "b2b" in text_lower:
        flags["back_to_back"] = True
        score -= 1
        deductions.append("Back-to-back fatigue (-1)")

    # High variance — wide CI relative to point estimate
    ci_width = prediction.ci_high - prediction.ci_low
    if ci_width > 0.40:
        flags["high_variance"] = True
        score -= 1
        deductions.append("High posterior variance, CV-equivalent > 0.5 (-1)")

    # Conflicting signals — does any Tier 1-2 source disagree with the aggregate?
    aggregate_sign = 1 if prediction.delta_log_odds > 0.05 else (-1 if prediction.delta_log_odds < -0.05 else 0)
    if aggregate_sign != 0:
        for ev in events:
            β = beta_for(ev.entity or ev.source.value)
            if β < 0.50:
                continue  # only count Tier 1-2
            polarity = {"positive": 1, "negative": -1, "neutral": 0}.get(ev.sentiment.value, 0)
            if polarity != 0 and polarity != aggregate_sign:
                flags["conflicting_signals"] = True
                score -= 1
                deductions.append("Tier 1-2 source contradicts aggregate (-1)")
                break

    # Bonus: 3+ Tier 1-2 sources agree
    tier12_aligned = 0
    for ev in events:
        β = beta_for(ev.entity or ev.source.value)
        if β < 0.50:
            continue
        polarity = {"positive": 1, "negative": -1, "neutral": 0}.get(ev.sentiment.value, 0)
        if polarity == aggregate_sign and aggregate_sign != 0:
            tier12_aligned += 1
    if tier12_aligned >= 3:
        score += 1
        bonuses.append("3+ Tier 1-2 sources corroborate (+1)")

    score = max(CONFIDENCE_FLOOR, min(10, score))
    return ConfidenceBreakdown(score=score, deductions=deductions, bonuses=bonuses, flags=flags)


def make_decision(
    prediction: Prediction,
    market_price: float,
    events: list[SentimentEvent],
) -> DecisionResult:
    edge = prediction.probability - market_price
    conf = compute_confidence(events, prediction, market_price)
    saturated = market_price >= SATURATED_HIGH or market_price <= SATURATED_LOW

    if saturated:
        # No actionable edge in a saturated market regardless of any small
        # numeric disagreement. Force NO_BET.
        decision: Decision = "NO_BET"
    elif abs(edge) < EDGE_NOISE_THRESHOLD or conf.score < CONFIDENCE_BET_FLOOR:
        decision = "NO_BET"
    elif edge >= EDGE_ACTIONABLE_THRESHOLD:
        decision = "BET_OVER"
    elif edge <= -EDGE_ACTIONABLE_THRESHOLD:
        decision = "BET_UNDER"
    else:
        decision = "NO_BET"  # 3-5pp edge isn't enough per v2.0

    # Risk level
    if decision == "NO_BET":
        risk: RiskLevel = "LOW"
    elif conf.flags.get("conflicting_signals"):
        risk = "HIGH"
    elif conf.score >= 8 and abs(edge) >= 0.07:
        risk = "LOW"
    else:
        risk = "MEDIUM"

    # Reasoning — saturated case gets a special, didactic explanation since
    # this is the most common source of "why doesn't it bet?" confusion.
    if saturated:
        if market_price >= SATURATED_HIGH:
            side, payout_pp = "YES", (1.0 / market_price - 1.0) * 100
            reason = (
                f"Market is already pricing YES at {market_price*100:.1f}% — the model "
                f"{'agrees' if abs(edge) < 0.01 else 'is close to market'} "
                f"({prediction.probability*100:.1f}%). A YES bet at this price pays only "
                f"{payout_pp:.2f}¢ per dollar risked, so there's no edge to capture even "
                f"though the outcome is nearly certain. Alpha Edge looks for mispricings, "
                f"not predictions; a near-certain outcome priced as near-certain has no "
                f"betting edge."
            )
        else:
            side, payout_pp = "NO", (1.0 / (1.0 - market_price) - 1.0) * 100
            reason = (
                f"Market is already pricing NO at {(1-market_price)*100:.1f}% (YES at "
                f"{market_price*100:.1f}%). The model {prediction.probability*100:.1f}% "
                f"agrees the outcome will most likely be NO. A NO bet at this price pays "
                f"only {payout_pp:.2f}¢ per dollar risked — not actionable."
            )
    elif decision == "NO_BET":
        if abs(edge) < EDGE_NOISE_THRESHOLD:
            reason = (
                f"Model {prediction.probability*100:.1f}% vs market "
                f"{market_price*100:.1f}% — edge of {edge*100:+.1f}pp is below the 3pp "
                f"noise threshold. Model and market agree."
            )
        elif conf.score < CONFIDENCE_BET_FLOOR:
            reason = f"Confidence {conf.score}/10 is below bet floor of {CONFIDENCE_BET_FLOOR}/10."
        else:
            reason = f"Edge {edge*100:+.1f}pp is in the lean range (3-5pp); v2.0 spec requires ≥5pp."
    else:
        side = "Over" if decision == "BET_OVER" else "Under"
        agg = "supportive" if (prediction.delta_log_odds * (1 if decision == "BET_OVER" else -1)) > 0 else "neutral"
        reason = (
            f"Model {prediction.probability*100:.1f}% vs market {market_price*100:.1f}% "
            f"gives {edge*100:+.1f}pp edge to {side}. Sentiment is {agg} "
            f"(Δℓ = {prediction.delta_log_odds:+.3f}). Confidence {conf.score}/10."
        )

    # Outcome forecast — distinct from the bet rec
    p = prediction.probability
    if p >= 0.70:
        forecast: OutcomeForecast = "YES"
    elif p <= 0.30:
        forecast = "NO"
    else:
        forecast = "UNCERTAIN"

    return DecisionResult(
        decision=decision,
        risk_level=risk,
        edge=edge,
        confidence=conf.score,
        confidence_breakdown=conf,
        reasoning=reason,
        outcome_forecast=forecast,
        outcome_forecast_pct=p,
        saturated_market=saturated,
    )
