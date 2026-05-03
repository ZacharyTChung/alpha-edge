"use client";

import { useState } from "react";

interface Term {
  label: string;
  short: string;
  detail: string;
  range?: string;
}

const TIER_TERMS: Term[] = [
  {
    label: "STRONG",
    short: "≥ +10pp edge — model strongly favors YES vs market",
    detail:
      "Our posterior probability is at least 10 percentage points above the market's YES price. This is the highest-conviction bullish signal — the system is saying the market is meaningfully underpricing YES. Treat as a candidate for sized betting (with fractional Kelly), not a guarantee.",
  },
  {
    label: "LEAN",
    short: "+4pp to +10pp edge — model leans YES",
    detail:
      "Modest disagreement with the market in the YES direction. Worth tracking but lower conviction than STRONG. Often these resolve toward zero edge as more sentiment lands or the market reprices.",
  },
  {
    label: "NONE",
    short: "Within ±4pp of market price",
    detail:
      "Model and market are essentially in agreement. No actionable edge in either direction. Most markets sit here — that's expected; markets are mostly efficient.",
  },
  {
    label: "FADE",
    short: "≤ −10pp edge — model strongly favors NO",
    detail:
      "Our posterior is at least 10pp below the market's YES price — market is overpricing YES. Either bet NO directly or treat as a sell signal if you already hold YES.",
  },
];

const SIGNAL_TERMS: Term[] = [
  {
    label: "Model probability",
    short: "Our Bayesian posterior for the YES outcome",
    detail:
      "Computed by taking the market price as a prior and applying a Bayesian update from weighted sentiment. Formula: posterior_log_odds = log_odds(market_price) + 0.6 × Σ(sentiment_score × credibility × novelty) / Σ(credibility × novelty).",
    range: "0% – 100%",
  },
  {
    label: "Confidence interval",
    short: "Heuristic range around the model probability",
    detail:
      "Width scales inversely with √(number of evidence pieces) and grows with dispersion across sources. Currently a heuristic — Phase 2 will replace this with proper Monte Carlo over component distributions. Treat narrow CIs as 'we have lots of consistent evidence' and wide CIs as 'few or contradictory data points'.",
    range: "always brackets the model probability",
  },
  {
    label: "Market price (YES)",
    short: "Last-traded price for the YES side, expressed as probability",
    detail:
      "Polymarket and Kalshi quote prices in dollars where $1.00 = 100% probability. We display this as the implied probability the market assigns to YES.",
    range: "0% – 100%",
  },
  {
    label: "Edge",
    short: "model_probability − market_price",
    detail:
      "The headline disagreement metric. Positive = we think the market underprices YES. Negative = we think the market overprices YES. Always shown in percentage points (pp).",
    range: "−100pp to +100pp (typical: −15 to +15)",
  },
  {
    label: "Tier",
    short: "Discrete bucket derived from edge magnitude",
    detail:
      "STRONG / LEAN / NONE / FADE. See the tier explanations above for thresholds and trading interpretation.",
  },
  {
    label: "Sentiment / stats weight",
    short: "How much each layer drove this signal",
    detail:
      "Sentiment weight = min(0.6, 0.1 + 0.05 × n_evidence). More evidence pieces = more sentiment influence, capped at 60%. Stats weight is the remainder. Right now stats weight is just the prior weight (since the prior is the market price); Phase 2 introduces a real statistical prior.",
    range: "each component 0 – 1, sum to 1",
  },
  {
    label: "Sentiment score",
    short: "Weighted average sentiment across all evidence",
    detail:
      "Aggregate of (positive=+1, neutral=0, negative=−1) for each text, weighted by source credibility × Claude's relevance × confidence. Strongly positive (~+0.5+) means the corpus broadly supports YES; negative means the corpus supports NO.",
    range: "−1 to +1",
  },
];

const EVIDENCE_TERMS: Term[] = [
  {
    label: "Sentiment label",
    short: "Polarity of the text relative to the market's YES outcome",
    detail:
      "When LLM-classified: Claude reads the text in the context of the specific market question and decides whether it pushes toward YES (positive), NO (negative), or neither (neutral). Without LLM (VADER fallback): a rule-based polarity score that doesn't understand market context — much noisier.",
  },
  {
    label: "Relevance",
    short: "How directly the text relates to the market (0 – 1)",
    detail:
      "Claude's estimate of whether this text is actually about the market in question. Low values (< 0.2) get filtered out before persistence. High values (> 0.7) indicate clear, on-topic information like an injury report for a specific player or a Fed decision for an interest-rate market.",
    range: "0 – 1",
  },
  {
    label: "Credibility",
    short: "Source-baseline trust × Claude confidence on this text",
    detail:
      "Each source has a base credibility weight (RotoWire 0.9, ESPN 0.8, Reddit 0.4, etc.). The LLM scales it by (0.5 + 0.5 × confidence) so a low-confidence Claude classification trims the source's nominal credibility, and a high-confidence classification preserves it. Bluesky and X posts also get an engagement modifier (likes / reposts).",
    range: "0 – 1",
  },
  {
    label: "LLM reasoning",
    short: "Claude's one-sentence justification for its classification",
    detail:
      "Shown as italicized text below each evidence row. This is *not* the system's reasoning for the bet — it's Claude's per-text rationale ('Game summary reference exists but no winner detail' or 'Direct injury report from credible wire'). Use it to sanity-check the relevance and sentiment scores.",
  },
];

const SOURCE_TERMS: Term[] = [
  {
    label: "news:rotowire",
    short: "Sports-specialist injury wire",
    detail:
      "RotoWire publishes per-player injury, status, and lineup news. Highest credibility for sports markets (0.9). Format is consistent — '<Player>: <status> for <event>'.",
  },
  {
    label: "news:espn / news:espn-api",
    short: "Mainstream sports media",
    detail:
      "Broad NBA/NFL/MLB coverage. ESPN news API returns structured JSON; the RSS feeds give us general headlines. Credibility ~0.8.",
  },
  {
    label: "news:google",
    short: "Per-market query against Google News",
    detail:
      "We send the market's entity terms (e.g. 'Lakers Nuggets', 'LeBron injury') to Google News with a 1-day recency filter. High-precision per market. Credibility depends on the underlying publisher.",
  },
  {
    label: "news:hn",
    short: "Hacker News (Algolia search)",
    detail:
      "Only used for finance/political markets — sports markets skip HN. Credibility scaled by HN points (≥500 = 0.75).",
  },
  {
    label: "reddit:*",
    short: "Per-subreddit RSS feeds",
    detail:
      "r/nba, r/sportsbook, r/nfl, r/soccer, r/kalshimarkets. Public RSS — no API key needed. Lower credibility (0.3–0.4) but high volume; the LLM relevance filter does most of the noise reduction.",
  },
  {
    label: "bluesky:*",
    short: "Public Bluesky search",
    detail:
      "Per-market query against Bluesky's public AT Protocol. Many sports beat reporters have moved here. Credibility scaled by likes / reposts on the post.",
  },
  {
    label: "x:*",
    short: "X / Twitter via syndication",
    detail:
      "Hand-picked sports beat reporters (Shams Charania, Brian Windhorst, etc.) pulled from Twitter's public embed widget data. Returns 'popular' tweets only — not real-time chronological. Useful for catching breaking news that goes viral.",
  },
];

export function SignalGlossary() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 32, border: "1px solid var(--border)" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%",
          padding: "10px 16px",
          background: "transparent",
          color: "var(--fg)",
          border: "none",
          textAlign: "left",
          fontFamily: "inherit",
          fontSize: 13,
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ textTransform: "uppercase", letterSpacing: "0.05em" }}>
          What does each signal mean?
        </span>
        <span style={{ color: "var(--muted)", fontSize: 11 }}>{open ? "− hide" : "+ show"}</span>
      </button>
      {open ? (
        <div style={{ padding: "0 16px 20px" }}>
          <Section title="Signal Tiers" terms={TIER_TERMS} kind="tier" />
          <Section title="Latest Signal Metrics" terms={SIGNAL_TERMS} />
          <Section title="Sentiment Evidence Fields" terms={EVIDENCE_TERMS} />
          <Section title="Sources" terms={SOURCE_TERMS} compact />
        </div>
      ) : null}
    </div>
  );
}

function Section({
  title,
  terms,
  kind,
  compact,
}: {
  title: string;
  terms: Term[];
  kind?: "tier";
  compact?: boolean;
}) {
  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
          marginBottom: 8,
          paddingBottom: 4,
          borderBottom: "1px solid var(--border)",
        }}
      >
        {title}
      </div>
      <dl style={{ margin: 0 }}>
        {terms.map((t) => (
          <div key={t.label} style={{ marginBottom: compact ? 8 : 12 }}>
            <dt
              style={{
                fontWeight: "normal",
                fontSize: 13,
                marginBottom: 2,
                color: kind === "tier" ? `var(--${tierVar(t.label)})` : "var(--fg)",
              }}
              className={kind === "tier" ? `tier-${t.label}` : undefined}
            >
              {t.label}
              {t.range ? (
                <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: 8 }}>
                  ({t.range})
                </span>
              ) : null}
            </dt>
            <dd style={{ margin: 0, color: "var(--muted)", fontSize: 12, lineHeight: 1.5 }}>
              <div>{t.short}</div>
              {!compact ? (
                <div style={{ marginTop: 4, fontSize: 11 }}>{t.detail}</div>
              ) : (
                <div style={{ marginTop: 2, fontSize: 11 }}>{t.detail}</div>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function tierVar(label: string): string {
  if (label === "STRONG") return "accent";
  if (label === "FADE") return "bad";
  return "fg";
}
