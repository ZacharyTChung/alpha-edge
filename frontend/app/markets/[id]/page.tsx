import { api, type MarketCalculation, type SentimentEvent, type Signal } from "@/lib/api";
import { InfoTip } from "@/app/components/info-tip";
import { SignalGlossary } from "@/app/components/signal-glossary";
import { CalculationPanel } from "./calculation-panel";
import { ReclassifyButton } from "./reclassify-button";
import { SignalChart } from "./signal-chart";

export const dynamic = "force-dynamic";

export default async function MarketDetailPage({
  params,
}: {
  params: { id: string };
}) {
  let market: Awaited<ReturnType<typeof api.getMarket>> | null = null;
  let signals: Signal[] = [];
  let sentiment: SentimentEvent[] = [];
  let calc: MarketCalculation | null = null;
  let error: string | null = null;
  try {
    [market, signals, sentiment] = await Promise.all([
      api.getMarket(params.id),
      api.getMarketSignals(params.id),
      api.getMarketSentiment(params.id),
    ]);
    try {
      calc = await api.getMarketCalculation(params.id);
    } catch {
      calc = null;
    }
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error || !market) {
    return (
      <section>
        <h2>Market unavailable</h2>
        <p>API error: {error ?? "no market"}</p>
      </section>
    );
  }

  const latest: Signal | undefined = signals[0];

  // Split LLM-classified events from VADER fallback. LLM events have
  // llm_reasoning populated; VADER events default to relevance_score=1.0.
  const llmEvents = sentiment
    .filter((e) => e.llm_reasoning)
    .sort((a, b) => b.relevance_score * b.credibility_weight - a.relevance_score * a.credibility_weight);
  const vaderEvents = sentiment
    .filter((e) => !e.llm_reasoning)
    .sort((a, b) => b.credibility_weight - a.credibility_weight);
  const showLLMOnly = llmEvents.length > 0;

  return (
    <section>
      <h2>{market.question_text}</h2>
      <p style={{ color: "var(--muted)" }}>
        {market.platform} · {market.category} · liquidity{" "}
        {market.liquidity > 0 ? `$${market.liquidity.toLocaleString()}` : "—"} · closes{" "}
        {new Date(market.close_time).toLocaleString()}
      </p>

      {latest ? (
        <>
          <h3 style={{ marginTop: 24 }}>Latest Signal</h3>
          <table style={{ maxWidth: 520 }}>
            <tbody>
              <tr>
                <th>
                  Model probability
                  <InfoTip>
                    Our Bayesian posterior for the YES outcome. Computed from{" "}
                    <code>log_odds(market_price) + 0.6 × weighted_sentiment</code>. Values close
                    to the market price mean evidence is mixed; large gaps mean sentiment moved
                    our estimate away from market consensus.
                  </InfoTip>
                </th>
                <td>{(latest.model_probability * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <th>
                  Confidence interval
                  <InfoTip>
                    Heuristic range around the model probability. Width scales with √(evidence
                    count) and dispersion across sources. Narrow CI = lots of consistent
                    evidence; wide CI = few or contradictory data points. Phase 2 will replace
                    this with proper Monte Carlo over component distributions.
                  </InfoTip>
                </th>
                <td>
                  {(latest.confidence_interval_low * 100).toFixed(1)}% –{" "}
                  {(latest.confidence_interval_high * 100).toFixed(1)}%
                </td>
              </tr>
              <tr>
                <th>
                  Market price (YES)
                  <InfoTip>
                    Last-traded price for the YES contract on Polymarket / Kalshi, expressed as
                    the implied probability the market assigns to YES.
                  </InfoTip>
                </th>
                <td>{(latest.market_price * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <th>
                  Edge
                  <InfoTip>
                    <code>model_probability − market_price</code>, in percentage points. Positive
                    = the market underprices YES (buy YES). Negative = the market overprices YES
                    (buy NO or pass). Tier thresholds: STRONG ≥ +10pp, LEAN ≥ +4pp, FADE ≤ −10pp.
                  </InfoTip>
                </th>
                <td
                  style={{
                    color: latest.edge > 0 ? "var(--accent)" : "var(--bad)",
                  }}
                >
                  {latest.edge >= 0 ? "+" : ""}
                  {(latest.edge * 100).toFixed(2)}pp
                </td>
              </tr>
              <tr>
                <th>
                  Tier
                  <InfoTip>
                    Discrete bucket from edge magnitude. STRONG and FADE are actionable bets;
                    LEAN is worth watching; NONE means the model agrees with the market. See
                    the glossary below for trading interpretation.
                  </InfoTip>
                </th>
                <td className={`tier-${latest.signal_tier}`}>{latest.signal_tier}</td>
              </tr>
              <tr>
                <th>
                  Sentiment / stats weight
                  <InfoTip>
                    How the model split influence between sentiment evidence and the statistical
                    prior. Sentiment weight = min(0.6, 0.1 + 0.05 × n_evidence) — more evidence
                    = more sentiment influence, capped at 60%. Currently the "stats" prior is
                    just the market price; Phase 2 introduces a real player-level regression.
                  </InfoTip>
                </th>
                <td>
                  {(latest.sentiment_weight * 100).toFixed(0)}% /{" "}
                  {(latest.stats_weight * 100).toFixed(0)}%
                </td>
              </tr>
              <tr>
                <th>
                  Sentiment score
                  <InfoTip>
                    Aggregate of (positive=+1, neutral=0, negative=−1) for each text, weighted
                    by source credibility × Claude relevance × confidence. Strongly positive
                    (≥ +0.5) = corpus broadly supports YES. Strongly negative = corpus supports
                    NO. Around 0 = mixed or thin evidence.
                  </InfoTip>
                </th>
                <td>{latest.sentiment_score.toFixed(3)}</td>
              </tr>
              {calc ? (
                <tr>
                  <th>
                    Quarter Kelly
                    <InfoTip>
                      Recommended bet size as a fraction of bankroll using fractional (¼)
                      Kelly. Formula: f* = (b·p − q) / b where b = 1/market_price − 1. ¼ Kelly
                      is conservative — full Kelly is theoretically optimal but assumes the
                      model probability is exactly correct.
                    </InfoTip>
                  </th>
                  <td
                    style={{
                      color:
                        calc.betting.quarter_kelly_pct_bankroll > 0
                          ? "var(--accent)"
                          : "var(--muted)",
                    }}
                  >
                    {calc.betting.quarter_kelly_pct_bankroll.toFixed(2)}% of bankroll
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>

          {signals.length > 1 ? (
            <>
              <h3 style={{ marginTop: 32 }}>
                Signal Trajectory
                <InfoTip>
                  Each refresh writes a new signal row. The chart plots model probability (green)
                  vs market price (white) over time. The shaded zone between them is the live
                  edge — green means we currently favor YES, red means we favor NO. Hover for
                  point-in-time values.
                </InfoTip>
              </h3>
              <SignalChart signals={signals} />
            </>
          ) : null}

          {calc ? <CalculationPanel calc={calc} /> : null}
        </>
      ) : (
        <p>No signals generated yet for this market.</p>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 32,
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <h3 style={{ margin: 0 }}>
          Sentiment Evidence
          <InfoTip>
            Texts ranked by relevance × credibility. Claude reads each in market context and
            scores how directly it relates. Texts judged irrelevant (relevance &lt; 0.2) are
            dropped before reaching this list.
          </InfoTip>
        </h3>
        <ReclassifyButton marketId={market.id} />
      </div>

      {sentiment.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 12 }}>No sentiment events captured yet.</p>
      ) : (
        <>
          {showLLMOnly ? null : (
            <p
              style={{
                color: "var(--warn)",
                fontSize: 12,
                marginTop: 8,
                marginBottom: 0,
              }}
            >
              ⚠️ All events here are VADER-fallback classifications — they were ingested before
              the LLM ran for this market and may not align with the question. Click "Reclassify
              with Claude" above to re-score and drop off-topic events.
            </p>
          )}

          {llmEvents.length > 0 ? (
            <EvidenceTable events={llmEvents.slice(0, 30)} />
          ) : (
            <EvidenceTable events={vaderEvents.slice(0, 30)} muted />
          )}

          {showLLMOnly && vaderEvents.length > 0 ? (
            <details style={{ marginTop: 16 }}>
              <summary
                style={{
                  cursor: "pointer",
                  color: "var(--muted)",
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                + show {vaderEvents.length} VADER-only events (likely lower quality)
              </summary>
              <div style={{ marginTop: 12 }}>
                <EvidenceTable events={vaderEvents.slice(0, 30)} muted />
              </div>
            </details>
          ) : null}
        </>
      )}

      <h3 style={{ marginTop: 32 }}>Signal History</h3>
      <table>
        <thead>
          <tr>
            <th>Generated</th>
            <th style={{ textAlign: "right" }}>Model P</th>
            <th style={{ textAlign: "right" }}>Market</th>
            <th style={{ textAlign: "right" }}>Edge</th>
            <th>Tier</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.id}>
              <td style={{ color: "var(--muted)", fontSize: 12 }}>
                {new Date(s.generated_at).toLocaleString()}
              </td>
              <td style={{ textAlign: "right" }}>{(s.model_probability * 100).toFixed(1)}%</td>
              <td style={{ textAlign: "right" }}>{(s.market_price * 100).toFixed(1)}%</td>
              <td
                style={{
                  textAlign: "right",
                  color: s.edge > 0 ? "var(--accent)" : "var(--bad)",
                }}
              >
                {s.edge >= 0 ? "+" : ""}
                {(s.edge * 100).toFixed(2)}
              </td>
              <td className={`tier-${s.signal_tier}`}>{s.signal_tier}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <SignalGlossary />
    </section>
  );
}

function EvidenceTable({ events, muted }: { events: SentimentEvent[]; muted?: boolean }) {
  return (
    <table style={{ marginTop: 12, opacity: muted ? 0.7 : 1 }}>
      <thead>
        <tr>
          <th>When</th>
          <th>Source</th>
          <th>Sentiment</th>
          <th style={{ textAlign: "right" }}>Rel</th>
          <th style={{ textAlign: "right" }}>Cred</th>
          <th>Snippet / LLM Reasoning</th>
        </tr>
      </thead>
      <tbody>
        {events.map((s) => (
          <tr key={s.id}>
            <td style={{ color: "var(--muted)", fontSize: 12 }}>
              {new Date(s.detected_at).toLocaleString()}
            </td>
            <td>
              {s.source_url ? (
                <a href={s.source_url} target="_blank" rel="noreferrer">
                  {s.source}
                </a>
              ) : (
                s.source
              )}
            </td>
            <td className={`sentiment-${s.sentiment}`}>{s.sentiment}</td>
            <td style={{ textAlign: "right", color: "var(--muted)" }}>
              {s.relevance_score.toFixed(2)}
            </td>
            <td style={{ textAlign: "right", color: "var(--muted)" }}>
              {s.credibility_weight.toFixed(2)}
            </td>
            <td style={{ maxWidth: 520 }}>
              <div>{s.raw_text.slice(0, 200)}</div>
              {s.llm_reasoning ? (
                <div
                  style={{
                    color: "var(--muted)",
                    fontSize: 11,
                    marginTop: 4,
                    fontStyle: "italic",
                  }}
                >
                  ↳ {s.llm_reasoning}
                </div>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
