"""Bayesian fusion: combine market-implied prior with weighted sentiment evidence.

Math (this is the load-bearing block — every endpoint downstream consumes these numbers):

  Prior log-odds:
      ℓ₀ = log(p_market / (1 − p_market))

  Per-evidence log-likelihood-ratio (signed Bayes factor):
      x_i = sentiment_score_i × relevance_i × confidence_i        ∈ [−1, +1]
      ℓr_i = β_source(i) × x_i

  Per-source contribution (cap to bound independence violation):
      ℓr_S = clip( Σ_{i ∈ S} ℓr_i, −K_MAX_SOURCE, +K_MAX_SOURCE )
  This prevents 17 tweets quoting the same beat reporter from outweighing one
  RotoWire injury report. K_MAX_SOURCE = 0.8 (≈ 19pp shift at p=0.5).

  Total evidence shift:
      Δℓ = Σ_S ℓr_S

  Posterior log-odds and probability:
      ℓ_post = ℓ₀ + Δℓ
      p_post = σ(ℓ_post) = 1 / (1 + e^{−ℓ_post})
      edge = p_post − p_market

  Variance / credible interval:
      Var(ℓr_i) ≈ (β_source(i) · (1 − relevance_i · confidence_i))²
      Var(ℓ_post) = Σ_i Var(ℓr_i)  +  σ_prior²       (σ_prior² = 0.05 baseline)
      ℓ_low, ℓ_high = ℓ_post ± 1.96 · √Var
      ci_low, ci_high = σ(ℓ_low), σ(ℓ_high)

  Quarter-Kelly bet size at the market YES price b:
      b = 1/p_market − 1                              (decimal odds − 1)
      f* = (b · p_post − (1 − p_post)) / b
      f_kelly = max(0, 0.25 · f*)

β_source comes from `sentiment.credibility`. Default base coefficients are
plausible priors (RotoWire 0.55, ESPN 0.40, anonymous Reddit 0.10); once we
have resolved markets, these get *learned* from outcomes via the credibility
table — see `sentiment/credibility.py`.
"""
from __future__ import annotations

import math
import random
from hashlib import sha256
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db.models import (
    Market,
    SentimentEvent,
    SentimentLabel,
    Signal,
)
from alpha_edge.market.edge import classify_tier
from alpha_edge.model.bayesian import from_log_odds, log_odds
from alpha_edge.sentiment.credibility import beta_for

# Caps and priors
K_MAX_SOURCE = 0.8       # max |log-LR| any single source can contribute
SIGMA_PRIOR_BASELINE = 0.225  # σ when there is zero evidence (≈ ±18pp at p=0.5)
NO_EVIDENCE_HALFWIDTH = 0.10  # CI halfwidth used when n_evidence == 0


@dataclass
class SourceContribution:
    source_key: str
    n_events: int
    raw_logLR: float            # Σ_i β · x_i, before clipping
    capped_logLR: float         # after clip to ±K_MAX_SOURCE
    avg_signed_score: float     # mean of x_i, useful for display
    beta: float                 # source predictive coefficient
    variance: float             # Σ Var(ℓr_i)


@dataclass
class Prediction:
    probability: float
    ci_low: float
    ci_high: float
    sentiment_score: float
    sentiment_weight: float
    stats_weight: float
    n_evidence: int
    # New numerical breakdown — exposed for the UI and the calculation endpoint
    prior_log_odds: float = 0.0
    delta_log_odds: float = 0.0
    posterior_log_odds: float = 0.0
    variance_log_odds: float = 0.0
    sigma_log_odds: float = 0.0
    contributions: list[SourceContribution] = field(default_factory=list)


def _signed_score(label: SentimentLabel, relevance: float, confidence_proxy: float) -> float:
    """x_i ∈ [−1, +1] — signed evidence strength.

    `confidence_proxy` is novelty for backward-compat (events ingested before
    we tracked LLM confidence have novelty=1.0 by default). Clip to [0, 1].
    """
    polarity = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(label.value, 0.0)
    r = max(0.0, min(1.0, float(relevance)))
    c = max(0.0, min(1.0, float(confidence_proxy)))
    return polarity * r * c


def _monte_carlo_credible_interval(
    posterior_log_odds: float,
    sigma_log_odds: float,
    samples: int = 4096,
) -> tuple[float, float]:
    """Estimate a 95% interval by sampling posterior log-odds.

    This keeps the interval stable for the UI while moving the implementation
    away from a purely analytic +/- 1.96σ shortcut.
    """
    if sigma_log_odds <= 0:
        p = from_log_odds(posterior_log_odds)
        return p, p

    seed_bytes = sha256(f"{posterior_log_odds:.6f}:{sigma_log_odds:.6f}:{samples}".encode())
    rng = random.Random(int.from_bytes(seed_bytes.digest()[:8], "big"))
    draws = [from_log_odds(rng.gauss(posterior_log_odds, sigma_log_odds)) for _ in range(samples)]
    draws.sort()
    low_idx = max(0, int(0.025 * (samples - 1)))
    high_idx = min(samples - 1, int(0.975 * (samples - 1)))
    return draws[low_idx], draws[high_idx]


def predict_market(
    db: Session,
    market: Market,
    market_price: float,
) -> Prediction:
    """Bayesian posterior given the latest sentiment events for `market`.

    Returns a Prediction with the full numerical breakdown (per-source
    contributions, variance, log-odds at each step) so callers can render
    the math explicitly.
    """
    if not 0.0 < market_price < 1.0:
        market_price = max(0.01, min(0.99, market_price))

    prior_lo = log_odds(market_price)

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
            ci_low=max(0.0, market_price - NO_EVIDENCE_HALFWIDTH),
            ci_high=min(1.0, market_price + NO_EVIDENCE_HALFWIDTH),
            sentiment_score=0.0,
            sentiment_weight=0.0,
            stats_weight=1.0,
            n_evidence=0,
            prior_log_odds=prior_lo,
            delta_log_odds=0.0,
            posterior_log_odds=prior_lo,
            variance_log_odds=SIGMA_PRIOR_BASELINE ** 2,
            sigma_log_odds=SIGMA_PRIOR_BASELINE,
        )

    # 1. Group events by source key (entity is the canonical handle/feed key
    # that we set during scraping; fall back to the source enum value).
    by_source: dict[str, list[SentimentEvent]] = defaultdict(list)
    for ev in events:
        key = _source_key(ev)
        by_source[key].append(ev)

    # 2. For each source, sum signed log-LR contributions and clip
    contributions: list[SourceContribution] = []
    delta_lo = 0.0
    variance = SIGMA_PRIOR_BASELINE ** 2 * 0.04  # tiny prior variance — most uncertainty comes from evidence
    score_sum_for_display = 0.0
    weight_for_display = 0.0
    for key, evs in by_source.items():
        beta = beta_for(key)
        raw = 0.0
        var_source = 0.0
        signed_sum = 0.0
        for ev in evs:
            x = _signed_score(ev.sentiment, ev.relevance_score, ev.novelty_score)
            raw += beta * x
            # Variance of a single log-LR: scales with how *unsure* we are.
            # When relevance=1 and novelty=1, the term is fully known → variance ≈ 0.
            # When relevance or novelty is low, variance grows toward β².
            unsureness = 1.0 - max(0.0, min(1.0, ev.relevance_score)) * max(0.0, min(1.0, ev.novelty_score))
            var_source += (beta * (0.3 + 0.7 * unsureness)) ** 2
            signed_sum += x
            score_sum_for_display += x * float(ev.credibility_weight)
            weight_for_display += float(ev.credibility_weight)
        capped = max(-K_MAX_SOURCE, min(K_MAX_SOURCE, raw))
        contributions.append(
            SourceContribution(
                source_key=key,
                n_events=len(evs),
                raw_logLR=raw,
                capped_logLR=capped,
                avg_signed_score=signed_sum / max(1, len(evs)),
                beta=beta,
                variance=var_source,
            )
        )
        delta_lo += capped
        variance += var_source

    sigma = math.sqrt(variance)
    posterior_lo = prior_lo + delta_lo
    posterior_p = from_log_odds(posterior_lo)

    ci_low, ci_high = _monte_carlo_credible_interval(posterior_lo, sigma)

    # Backward-compat display fields (sentiment_weight has no algorithmic meaning
    # under the new math but the schema still expects it). Express it as the
    # share of the *total log-odds magnitude* attributed to evidence vs. prior.
    if abs(prior_lo) + abs(delta_lo) > 1e-6:
        sentiment_weight = abs(delta_lo) / (abs(prior_lo) + abs(delta_lo))
    else:
        sentiment_weight = 0.0
    stats_weight = 1.0 - sentiment_weight
    aggregate = score_sum_for_display / max(weight_for_display, 1e-6)

    return Prediction(
        probability=posterior_p,
        ci_low=ci_low,
        ci_high=ci_high,
        sentiment_score=aggregate,
        sentiment_weight=sentiment_weight,
        stats_weight=stats_weight,
        n_evidence=len(events),
        prior_log_odds=prior_lo,
        delta_log_odds=delta_lo,
        posterior_log_odds=posterior_lo,
        variance_log_odds=variance,
        sigma_log_odds=sigma,
        contributions=sorted(contributions, key=lambda c: -abs(c.capped_logLR)),
    )


def _source_key(ev: SentimentEvent) -> str:
    """Stable source identifier used for credibility lookup + per-source caps.

    Resolution order:
      1. Parse the source_url — most reliable (e.g. rotowire.com → news:rotowire).
      2. Use the entity field if it already contains a `prefix:slug` shape.
      3. Fall back to the bare source enum value.
    """
    from urllib.parse import urlparse

    url = (ev.source_url or "").strip()
    src = ev.source.value
    if url:
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
        except Exception:
            host = url.lower()
            path = ""

        # News domain mapping
        if "rotowire.com" in host:
            return "news:rotowire"
        if "espn.com" in host or "site.api.espn.com" in host:
            return "news:espn"
        if "cbssports.com" in host:
            return "news:cbs"
        if "yahoo.com" in host:
            return "news:yahoo"
        if "news.google.com" in host or "google.com" in host:
            return "news:google"
        if "ycombinator.com" in host or "news.ycombinator.com" in host:
            return "news:hn"
        if "theathletic.com" in host:
            return "news:athletic"

        # Reddit subreddit
        if "reddit.com" in host and "/r/" in path:
            try:
                sub = path.split("/r/")[1].split("/")[0]
                return f"reddit:{sub}"
            except Exception:
                return "reddit:default"

        # Bluesky handle
        if "bsky.app" in host and "/profile/" in path:
            try:
                handle = path.split("/profile/")[1].split("/")[0]
                return f"bluesky:{handle}"
            except Exception:
                return "bluesky:default"

        # X / Twitter handle
        if "x.com" in host or "twitter.com" in host:
            try:
                # path like '/username/status/12345' or '/username'
                parts = [p for p in path.split("/") if p]
                if parts:
                    handle = parts[0]
                    return f"x:{handle}"
            except Exception:
                return "x:default"

    entity = (ev.entity or "").strip().lower()
    head = entity.split(",")[0].strip() if entity else ""
    if head and ":" in head and len(head.split(":", 1)[0]) <= 12:
        return head
    return src


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


def kelly_fraction_quarter(p_post: float, market_price: float) -> float:
    """Quarter-Kelly fraction (legacy alias). Prefer half_kelly_capped."""
    if not 0.0 < market_price < 1.0 or not 0.0 < p_post < 1.0:
        return 0.0
    b = (1.0 / market_price) - 1.0
    if b <= 0:
        return 0.0
    full = (b * p_post - (1.0 - p_post)) / b
    return max(0.0, 0.25 * full)
