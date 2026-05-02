import Link from "next/link";

import { api, type EdgeReportItem } from "@/lib/api";

export default async function EdgePage() {
  let items: EdgeReportItem[] = [];
  let error: string | null = null;
  try {
    items = await api.getEdgeReport();
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <section>
      <h2>Edge Report</h2>
      <p style={{ color: "var(--muted)" }}>
        Open markets sorted by absolute edge. Strong tier = ≥10% gap.
      </p>
      {error ? <p>API unreachable: {error}</p> : null}
      {!error && items.length === 0 ? <p>No edges above threshold.</p> : null}
      {items.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>Model</th>
              <th>Price</th>
              <th>Edge</th>
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.market_id}>
                <td>
                  <Link href={`/markets/${item.market_id}`}>{item.question_text}</Link>
                </td>
                <td>{(item.model_probability * 100).toFixed(1)}%</td>
                <td>{(item.market_price * 100).toFixed(1)}%</td>
                <td>{(item.edge * 100).toFixed(2)}</td>
                <td className={`tier-${item.signal_tier}`}>{item.signal_tier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
