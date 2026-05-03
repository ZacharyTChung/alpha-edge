import { api, type SentimentEvent, type Signal } from "@/lib/api";
import { InfoTip } from "@/app/components/info-tip";
import { SignalGlossary } from "@/app/components/signal-glossary";
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
  let error: string | null = null;
  try {
    [market, signals, sentiment] = await Promise.all([
      api.getMarket(params.id),
      api.getMarketSignals(params.id),
      api.getMarketSentiment(params.id),
    ]);
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

  // Sort sentiment by relevance × credibility so the most informative events lead.
  const ranked = [...sentiment].sort((a, b) => {
    const ra = a.relevance_score * a.credibility_weight;
    const rb = b.relevance_score * b.credibility_weight;
    return rb - ra;
  });

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
        </>
      ) : (
        <p>No signals generated yet for this market.</p>
      )}

      <h3 style={{ marginTop: 32 }}>
        Sentiment Evidence
        <InfoTip>
          Texts ranked by relevance × credibility. When the LLM is enabled, each text shows
          Claude's per-text reasoning underneath. Texts the LLM judged irrelevant (relevance &lt; 0.2)
          were filtered out before reaching this list.
        </InfoTip>
      </h3>
      {ranked.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>No sentiment events captured yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Source</th>
              <th>
                Sentiment
                <InfoTip>
                  Polarity relative to the YES outcome. With LLM: Claude reads the text in
                  market context. Without LLM (VADER fallback): rule-based polarity that
                  doesn't understand market context — much noisier.
                </InfoTip>
              </th>
              <th style={{ textAlign: "right" }}>
                Rel
                <InfoTip>
                  Relevance: how directly this text relates to the specific market (0–1).
                  Texts &lt; 0.2 were filtered. Texts &gt; 0.7 are clear, on-topic information.
                </InfoTip>
              </th>
              <th style={{ textAlign: "right" }}>
                Cred
                <InfoTip>
                  Credibility: source baseline (RotoWire 0.9, ESPN 0.8, Reddit 0.4) scaled by
                  Claude's confidence on this specific text. Engagement-weighted for Bluesky
                  and X posts.
                </InfoTip>
              </th>
              <th>Snippet / LLM Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {ranked.slice(0, 30).map((s) => (
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
