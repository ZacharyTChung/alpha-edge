"""Source credibility — predictive coefficients for the Bayesian update.

The number we expose, `beta_for(key)`, is the **predictive coefficient** that
multiplies a piece of evidence's signed score (sentiment × relevance × confidence)
to get its log-likelihood-ratio contribution. See `model.predict` for how it's
used.

Two parts:

1. PRIOR_BETA — hand-coded baseline coefficients (informed prior).
2. Learned posterior — once we have resolved markets, the SourceCredibility
   table tracks Beta(α, β) over directional accuracy. The posterior mean
   shrinks toward 0.5 when n is small. The final coefficient is then:

       β_source = β_prior · 2·(posterior_mean − 0.5) + β_prior · prior_weight
                = β_prior · accuracy_lift

   where `accuracy_lift` is in [−1, +2]: a source that's been right 80% of
   the time gets a 1.6× boost; a source that's been right 50% (no signal)
   gets the prior coefficient unchanged; a source consistently wrong gets
   a *negative* coefficient (we'll bet against its sentiment).

Until enough resolved markets land, `beta_for` returns the prior. The
update_source_outcome() helper accepts a (source_key, was_correct) tuple and
moves the Beta posterior, ready for the day we have outcome data.
"""
from __future__ import annotations

from threading import Lock
from typing import Iterable

# Tier-aligned predictive coefficients per v2.0 source spec.
#
# v2.0 tier weights (1.00 / 0.90 / 0.75 / 0.40) are normalized to log-LR shifts:
#   Tier 1 → β = 0.80   (~+18pp posterior shift at p=0.5 from one strong signal)
#   Tier 2 → β = 0.65
#   Tier 3 → β = 0.50
#   Tier 4 → β = 0.25
PRIOR_BETA: dict[str, float] = {
    # ── TIER 1: official team / league sources ────────────────────────────
    # (we don't currently scrape NBA injury report directly; once we do,
    #  add e.g. "nba:injury_report" → 0.80 here)

    # ── TIER 2: insider beat reporters (β = 0.65) ─────────────────────────
    "x:shamscharania": 0.65,
    "x:adamschefter": 0.65,
    "x:windhorstespn": 0.65,
    "x:chrisbhaynes": 0.65,
    "x:ken_rosenthal": 0.65,
    "x:marcjspears": 0.65,

    # ── TIER 3: established sports media (β = 0.50) ───────────────────────
    "news:rotowire": 0.55,           # specialist injury wire — slight bonus
    "news:athletic": 0.50,
    "news:espn": 0.50,
    "news:espn-api": 0.50,
    "news:cbs": 0.45,
    "news:yahoo": 0.45,

    # ── Targeted aggregators (β = 0.30) ───────────────────────────────────
    # Google News headlines come from any publisher — assume Tier 3-ish baseline,
    # discounted because we don't parse the underlying publisher reliably.
    "news:google": 0.35,
    "news:hn": 0.40,                 # high-engagement HN posts tend to have substance

    # ── TIER 4: community consensus (β = 0.25) ────────────────────────────
    "reddit:sportsbook": 0.25,       # sharpest community
    "reddit:nba": 0.20,
    "reddit:nfl": 0.20,
    "reddit:mlb": 0.20,
    "reddit:soccer": 0.20,
    "reddit:nhl": 0.20,
    "reddit:kalshimarkets": 0.18,
    "reddit:wallstreetbets": 0.12,
    # Bluesky engagement-weighted upstream; treat as Tier 4 baseline here
    "bluesky:default": 0.22,

    # Catch-all (anonymous, unverified)
    "default": 0.15,
}

# Range of the final coefficient — an extreme learned source can move
# the prior by up to ±30%, but we cap it so a few flukes don't blow up.
MIN_BETA = 0.05
MAX_BETA = 0.85

# Prior strength: pretend every source has been "right 5 times, wrong 5 times"
# before any data lands. Larger numbers slow learning; smaller numbers let
# tiny samples swing β too much.
PRIOR_PSEUDOCOUNTS = (5, 5)

# In-memory accuracy ledger. Persisted form (DB table) is the next step;
# this in-process dict is enough for the current API surface.
_accuracy: dict[str, list[int]] = {}
_lock = Lock()


def _normalize(key: str) -> str:
    if not key:
        return "default"
    k = key.strip().lower()
    # accept "x:Shams" or "x:shamscharania" interchangeably; collapse spaces
    k = k.replace(" ", "")
    return k


def prior_beta_for(key: str) -> float:
    return PRIOR_BETA.get(_normalize(key), PRIOR_BETA["default"])


def posterior_accuracy(key: str) -> tuple[float, int]:
    """Return (mean, n_observed) for the source's Beta(α,β) posterior.

    Beta(α=PRIOR+correct, β=PRIOR+wrong); mean = α / (α + β).
    n_observed counts only outcomes we've seen, *not* the prior pseudocount.
    """
    nk = _normalize(key)
    correct, wrong = _accuracy.get(nk, [0, 0])
    a = PRIOR_PSEUDOCOUNTS[0] + correct
    b = PRIOR_PSEUDOCOUNTS[1] + wrong
    return a / (a + b), correct + wrong


def beta_for(key: str) -> float:
    """Final predictive coefficient combining prior + observed accuracy.

    accuracy_lift = 2·(posterior_mean − 0.5)   ∈ [−1, +1]
    If we've seen no outcomes, lift = 0 (mean = 0.5) and β = prior unchanged.
    """
    nk = _normalize(key)
    base = prior_beta_for(nk)
    mean, n = posterior_accuracy(nk)
    lift = 2.0 * (mean - 0.5)
    # Shrink the lift when n is small (don't let 1 lucky hit triple our coef).
    shrink = n / (n + 10.0)  # at n=10, half weight; at n=50, ~0.83 weight
    final = base * (1.0 + lift * shrink)
    return max(MIN_BETA, min(MAX_BETA, final))


def update_source_outcome(key: str, was_correct: bool) -> None:
    """Increment the accuracy counter for a source.

    Called from the closing-line backtester once a market resolves: for every
    event that contributed to a signal which (correctly or incorrectly)
    predicted the resolution, bump the counter for its source.
    """
    nk = _normalize(key)
    with _lock:
        slot = _accuracy.setdefault(nk, [0, 0])
        if was_correct:
            slot[0] += 1
        else:
            slot[1] += 1


def all_known_sources() -> Iterable[str]:
    return list(PRIOR_BETA.keys())


def credibility_for(key: str) -> float:
    """Backward-compat shim. Returns a value in [0, 1] suitable for the old
    `credibility_weight` column on SentimentEvent. Maps β ∈ [MIN_BETA, MAX_BETA]
    linearly to [0.1, 0.95].
    """
    b = beta_for(key)
    span = MAX_BETA - MIN_BETA
    if span <= 0:
        return 0.5
    return 0.10 + ((b - MIN_BETA) / span) * (0.95 - 0.10)
