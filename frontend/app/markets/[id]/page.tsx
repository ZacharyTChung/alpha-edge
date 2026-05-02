import { api, type SentimentEvent, type Signal } from "@/lib/api";
import { PriceSparkline } from "./sparkline";

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
  // Signal history is returned newest-first; reverse for the sparkline timeline.
  const ordered = [...signals].reverse();
  const modelSeries = ordered.map((s) => s.model_probability);
  const marketSeries = ordered.map((s) => s.market_price);

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
        <div style={{ display: "flex", gap: 32, marginTop: 16, marginBottom: 24, flexWrap: "wrap" }}>
          <div style={{ flex: "0 0 auto" }}>
            <h3 style={{ marginTop: 0 }}>Latest Signal</h3>
            <table>
              <tbody>
                <tr>
                  <th>Model probability</th>
                  <td>{(latest.model_probability * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <th>Confidence interval</th>
                  <td>
                    {(latest.confidence_interval_low * 100).toFixed(1)}% –{" "}
                    {(latest.confidence_interval_high * 100).toFixed(1)}%
                  </td>
                </tr>
                <tr>
                  <th>Market price (YES)</th>
                  <td>{(latest.market_price * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <th>Edge</th>
                  <td
                    style={{
                      color: latest.edge > 0 ? "var(--accent)" : "var(--bad)",
                    }}
                  >
                    {latest.edge >= 0 ? "+" : ""}
                    {(latest.edge * 100).toFixed(2)}
                  </td>
                </tr>
                <tr>
                  <th>Tier</th>
                  <td className={`tier-${latest.signal_tier}`}>{latest.signal_tier}</td>
                </tr>
                <tr>
                  <th>Sentiment / stats wt</th>
                  <td>
                    {(latest.sentiment_weight * 100).toFixed(0)}% /{" "}
                    {(latest.stats_weight * 100).toFixed(0)}%
                  </td>
                </tr>
                <tr>
                  <th>Sentiment score</th>
                  <td>{latest.sentiment_score.toFixed(3)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {modelSeries.length > 1 ? (
            <div style={{ flex: "0 0 auto" }}>
              <h3 style={{ marginTop: 0 }}>Price History</h3>
              <PriceSparkline
                series={[
                  { values: modelSeries, color: "var(--accent)", label: "model" },
                  { values: marketSeries, color: "var(--muted)", label: "market" },
                ]}
              />
            </div>
          ) : null}
        </div>
      ) : (
        <p>No signals generated yet for this market.</p>
      )}

      <h3>Sentiment Evidence</h3>
      {ranked.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>No sentiment events captured yet.</p>
      ) : (
        <table>
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
    </section>
  );
}
