"""LLM-based sentiment classifier — replaces VADER when ANTHROPIC_API_KEY is set.

Why: VADER scores polarity but doesn't understand sports betting context. "Anthony
Davis questionable" reads neutral to VADER but is a clear negative likelihood
update for any AD-related market. An LLM understands the claim.

Design:
- Per-market batched call: one Anthropic request handles all texts for a single
  market. The market question gives Claude the context it needs to score relevance
  and impact direction.
- System prompt is large + frozen → cached with `cache_control: ephemeral`. After
  the first request, the system prompt is a ~90% discount cache read.
- Structured output via `messages.parse()` + Pydantic — guarantees parseable shape.
- Fail-soft: any error returns an empty list and the caller falls back to VADER.

Cost (claude-sonnet-4-6, with prompt caching warm):
- ~$0.005 per market for ~5 texts each. ~100 markets per refresh ≈ $0.50/refresh.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from alpha_edge.config import get_settings

log = logging.getLogger(__name__)

# Rich, frozen system prompt — sized to clear the 2048-token cache threshold for
# Sonnet 4.6 so prompt caching activates after the first call. Examples here are
# load-bearing: they shape calibration for the specific betting context, and they
# also push the prompt over the cache minimum.
SYSTEM_PROMPT = """You are a sports betting analyst evaluating text snippets for their impact on specific binary prediction markets (Kalshi, Polymarket).

For each text snippet, assign:
1. sentiment — "positive" | "negative" | "neutral" — overall tone toward the YES outcome of the specific market in the prompt
2. relevance — 0.0–1.0 — how directly the text relates to the specific market question
3. impact_direction — "yes" | "no" | "none" — which side of the binary outcome the text supports, if any
4. confidence — 0.0–1.0 — how strong/clear the signal is
5. reasoning — one short sentence (≤25 words)

CALIBRATION GUIDANCE

HIGH SIGNAL (relevance ≥ 0.7, confidence ≥ 0.7):
- Confirmed injury status from beat reporters, team announcements, or sports-specialist wires (RotoWire, ESPN, Athletic): "Player X ruled OUT for tonight's game"
- Direct quotes from players/coaches about availability, motivation, or strategy
- Statistical breakdowns with clear betting implications: "Team X is 12-2 ATS as home favorites in this scenario"
- Verified roster/lineup changes posted within 24h of the market resolution
- Officially announced ejections, suspensions, or starting lineup changes

MEDIUM SIGNAL (relevance 0.4–0.7, confidence 0.4–0.7):
- General team/player news within the past few days but without direct game implications
- Speculation from credible analysts (Woj, Shams, Schefter, beat writers) that isn't yet confirmed
- Recent performance context ("Player X has been struggling from three") without specific game-day relevance
- Context about the matchup, pace, or coaching strategy that's relevant but not decisive

LOW SIGNAL (relevance < 0.4, confidence < 0.4):
- Memes, jokes, fan reactions, hot takes from anonymous accounts
- Marketing or hype content (highlight reels, promo posts)
- Off-topic content that mentions the team/player but isn't about the market
- Stale information about a game that's already happened or a different game
- Generic season storylines (MVP race, awards) for a single-game market

EXAMPLES

Market: "Lakers win game 3 vs Nuggets?"

Text: "[source: news:rotowire] Anthony Davis (calf) ruled OUT for Game 3 vs the Nuggets. Will not travel with the team."
→ sentiment: negative, relevance: 0.95, impact_direction: no, confidence: 0.9
   reasoning: "AD ruling out is a major negative shock for Lakers' chances in Game 3."

Text: "[source: x:shamscharania] BREAKING: The Lakers and Nuggets have voted to boycott the NBA season."
→ sentiment: neutral, relevance: 0.1, impact_direction: none, confidence: 0.85
   reasoning: "This is from 2020 (boycott context); not relevant to a current game market."

Text: "[source: reddit:nba] Lakers in 6"
→ sentiment: positive, relevance: 0.3, impact_direction: yes, confidence: 0.2
   reasoning: "Generic fan prediction, no specific information; minimal signal."

Text: "[source: news:espn] LeBron James has had 'the greatest career of any NBA player', says JJ Redick"
→ sentiment: neutral, relevance: 0.05, impact_direction: none, confidence: 0.9
   reasoning: "Career retrospective with no Game 3 implications."

Market: "LeBron James scores 25+ points tonight?"

Text: "[source: bluesky:nbaanalyst] LeBron averaging 31 PPG in this series with the Nuggets sending Aaron Gordon as primary defender. Pace favors over."
→ sentiment: positive, relevance: 0.9, impact_direction: yes, confidence: 0.7
   reasoning: "Direct context on series scoring with matchup detail; supports OVER on 25+ points."

Text: "[source: reddit:sportsbook] hammering the under here, lebron looked gassed last game"
→ sentiment: negative, relevance: 0.5, impact_direction: no, confidence: 0.3
   reasoning: "Anecdotal observation from anonymous account; weak signal but directionally relevant."

Market: "Will the Fed cut rates in June?"

Text: "[source: news:hn] Federal Reserve signals likely 25bp cut in June meeting per Powell remarks at Jackson Hole — 1450 pts on HN"
→ sentiment: positive, relevance: 0.95, impact_direction: yes, confidence: 0.85
   reasoning: "Direct Fed Chair signal on June meeting; high-engagement HN coverage adds credibility."

Text: "[source: x:bettingpros] CPI print came in hot at 3.4%, Fed cut odds slipping fast"
→ sentiment: negative, relevance: 0.85, impact_direction: no, confidence: 0.7
   reasoning: "Hot inflation reduces probability of June cut; macro datapoint with direct relevance."

Text: "[source: reddit:sportsbook] random meme about JPOW"
→ sentiment: neutral, relevance: 0.05, impact_direction: none, confidence: 0.8
   reasoning: "Meme content with no informational signal."

Market: "BTC closes above $100k on June 1?"

Text: "[source: news:hn] SEC approves spot Bitcoin ETF expansion, institutional inflows expected — 980 pts"
→ sentiment: positive, relevance: 0.9, impact_direction: yes, confidence: 0.75
   reasoning: "ETF expansion is a legitimate price driver toward $100k threshold."

Text: "[source: bluesky:cryptotrader] BTC dumped 8% in last hour, liquidations cascading"
→ sentiment: negative, relevance: 0.95, impact_direction: no, confidence: 0.7
   reasoning: "Active price drop reduces probability of $100k close; depends on remaining time to resolution."

EDGE CASES

Time staleness — assume the market is current. If the text references events that clearly already happened (e.g. "Lakers won Game 1 last night" appearing for a Game 1 market with `close_time` already past, or news from prior seasons), drop relevance to ≤ 0.2 even if the topic matches.

Counterfactual / hypothetical — text framed as "if X happens" or "assuming Y" without a concrete claim should score lower confidence (≤ 0.4) regardless of how on-topic it appears.

Quoted reactions — a beat reporter quoting a fan or analyst is closer to medium signal (0.4–0.6 confidence). The credibility of the quoter does not transfer fully to the quoted opinion.

Negative-of-negative — "X is NOT injured" or "X will NOT be out" is a positive signal toward the player participating, not negative. Read the polarity of the underlying claim, not the surface words.

Translated / non-English text — if the text appears to be in another language, only classify if the meaning is clearly recoverable. Otherwise relevance ≤ 0.2.

Source-specific calibration:
- news:rotowire — sports-specialist wire, treat injury reports as high-confidence
- news:espn / news:espn-api — mainstream sports media, slightly less injury-specific but still reliable
- news:google — query-targeted from any source on the open web; weight by the underlying publisher mentioned in the title
- news:hn — finance/political/tech relevance only; high points indicate substance
- reddit:sportsbook — public betting community, high noise but occasional sharp insight
- reddit:nba / reddit:nfl — fan communities, treat non-news posts as low signal
- bluesky:* — varies; base credibility is set by engagement upstream, classify on content
- x:shamscharania, x:windhorst, x:schefter — high-credibility sports beat reporters
- twitter:* (live X API) — only present if user pays for Basic+ tier; assume current

GENERAL RULES

- Penalize anonymous social media accounts unless they cite credible sources.
- Penalize content that's clearly stale (game already played, different game, different season).
- Reward concrete, time-stamped information ("OUT for tonight", "ruled out 30 min ago") over vague statements ("might be questionable").
- Never invent details not in the text. If the text is ambiguous, lower confidence rather than guess.
- For markets you can't tell are sports, politics, or finance — reason from the literal text and assign relevance based on direct mention of the market's subject.
- For YES/NO markets where direction is genuinely unclear, use impact_direction: "none".

Reply with valid JSON matching the BatchClassification schema. Items must be in the same order as the input texts."""


class Classification(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: float = Field(ge=0.0, le=1.0)
    impact_direction: Literal["yes", "no", "none"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class BatchClassification(BaseModel):
    items: list[Classification]


def is_configured() -> bool:
    s = get_settings()
    return bool(s.anthropic_api_key)


_client_cache = None


def _client():
    global _client_cache
    if _client_cache is not None:
        return _client_cache
    import anthropic

    _client_cache = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    return _client_cache


def classify_for_market(
    market_question: str,
    texts: list[str],
    sources: list[str] | None = None,
    stats_context: str | None = None,
) -> list[Classification]:
    """Classify a batch of text snippets for their impact on a specific market.

    Returns one Classification per input text, in the same order. On any failure
    (no key, API error, rate limit) returns an empty list — caller should fall
    back to VADER.
    """
    if not is_configured() or not texts:
        return []
    if sources is None:
        sources = ["unknown"] * len(texts)
    elif len(sources) != len(texts):
        sources = (sources + ["unknown"] * len(texts))[: len(texts)]

    client = _client()
    user_lines = [f'Market question: "{market_question}"']
    if stats_context:
        user_lines.append(f"Stats context: {stats_context}")
    user_lines.extend(["", f"Classify these {len(texts)} texts (return items[] in order):"])
    for i, (txt, src) in enumerate(zip(texts, sources), start=1):
        snippet = (txt or "").strip().replace("\n", " ")[:400]
        user_lines.append(f"{i}. [source: {src}] {snippet}")

    try:
        resp = client.messages.parse(
            model=get_settings().anthropic_sentiment_model,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": "\n".join(user_lines)}],
            output_format=BatchClassification,
        )
    except Exception as e:
        log.warning("LLM classify failed: %s", e)
        return []

    parsed = resp.parsed_output
    if parsed is None:
        return []
    items = list(parsed.items)
    while len(items) < len(texts):
        items.append(
            Classification(
                sentiment="neutral",
                relevance=0.0,
                impact_direction="none",
                confidence=0.0,
                reasoning="LLM did not return a classification for this item",
            )
        )
    return items[: len(texts)]


def cache_diagnostics(
    market_question: str = "Will the Lakers win game 3?",
    text: str = "Lakers win in 6",
) -> dict:
    """One-shot call returning usage + cache stats — useful for sanity-checking.

    Run this twice: first call should report cache_creation_input_tokens > 0,
    cache_read_input_tokens == 0. Second call within 5 min should report
    cache_read_input_tokens > 0 (cache hit, ~10% of normal cost).
    """
    if not is_configured():
        return {"error": "ANTHROPIC_API_KEY not set"}
    client = _client()
    resp = client.messages.create(
        model=get_settings().anthropic_sentiment_model,
        max_tokens=500,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f'Market: "{market_question}"\n1. {text}'}],
    )
    u = resp.usage
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "model": resp.model,
    }
