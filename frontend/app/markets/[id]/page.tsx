import { api, type Signal } from "@/lib/api";

export default async function MarketDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const [market, signals] = await Promise.all([
    api.getMarket(params.id),
    api.getMarketSignals(params.id),
  ]);

  const latest: Signal | undefined = signals[0];

  return (
    <section>
      <h2>{market.question_text}</h2>
      <p style={{ color: "var(--muted)" }}>
        {market.platform} · {market.category} · closes {new Date(market.close_time).toLocaleString()}
      </p>

      {latest ? (
        <div>
          <h3>Latest Signal</h3>
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
                <th>Market price</th>
                <td>{(latest.market_price * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <th>Edge</th>
                <td>{(latest.edge * 100).toFixed(2)} bps</td>
              </tr>
              <tr>
                <th>Tier</th>
                <td className={`tier-${latest.signal_tier}`}>{latest.signal_tier}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <p>No signals generated yet for this market.</p>
      )}

      <h3>Signal History</h3>
      <table>
        <thead>
          <tr>
            <th>Generated</th>
            <th>Model P</th>
            <th>Market</th>
            <th>Edge</th>
            <th>Tier</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.id}>
              <td>{new Date(s.generated_at).toLocaleString()}</td>
              <td>{(s.model_probability * 100).toFixed(1)}%</td>
              <td>{(s.market_price * 100).toFixed(1)}%</td>
              <td>{(s.edge * 100).toFixed(2)}</td>
              <td className={`tier-${s.signal_tier}`}>{s.signal_tier}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
