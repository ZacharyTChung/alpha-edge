import Link from "next/link";

import { api, type Market } from "@/lib/api";

export default async function MarketsPage() {
  let markets: Market[] = [];
  let error: string | null = null;
  try {
    markets = await api.listMarkets();
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <section>
      <h2>Tracked Markets</h2>
      {error ? <p>API unreachable: {error}</p> : null}
      {!error && markets.length === 0 ? (
        <p>No markets ingested yet. Run the Phase 1 polling jobs.</p>
      ) : null}
      {markets.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              <th>Question</th>
              <th>Category</th>
              <th>Closes</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((market) => (
              <tr key={market.id}>
                <td>{market.platform}</td>
                <td>
                  <Link href={`/markets/${market.id}`}>{market.question_text}</Link>
                </td>
                <td>{market.category}</td>
                <td>{new Date(market.close_time).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
