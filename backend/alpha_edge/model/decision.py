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

# v2.0 thresholds
EDGE_NOISE_THRESHOLD = 0.03          # |edge| below 3pp = NO BET
EDGE_ACTIONABLE_THRESHOLD = 0.05     # need 5pp edge to recommend a bet
CONFIDENCE_BET_FLOOR = 7             # need confidence ≥ 7 to recommend
CONFIDENCE_FLOOR = 3                 # output never below this


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

    if abs(edge) < EDGE_NOISE_THRESHOLD or conf.score < CONFIDENCE_BET_FLOOR:
        decision: Decision = "NO_BET"
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

    # Reasoning
    if decision == "NO_BET":
        if abs(edge) < EDGE_NOISE_THRESHOLD:
            reason = f"Edge of {edge*100:+.1f}pp is below 3pp noise threshold."
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

    return DecisionResult(
        decision=decision,
        risk_level=risk,
        edge=edge,
        confidence=conf.score,
        confidence_breakdown=conf,
        reasoning=reason,
    )
