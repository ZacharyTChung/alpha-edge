import Link from "next/link";

import { api, type Market } from "@/lib/api";
import { RefreshButton } from "./refresh-button";
import { StatsBanner } from "./stats-banner";

export const dynamic = "force-dynamic";

function formatLiquidity(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>Tracked Markets</h2>
        <RefreshButton />
      </div>

      <StatsBanner />

      {error ? <p>API unreachable: {error}</p> : null}
      {!error && markets.length === 0 ? (
        <p>No markets ingested yet. Click Refresh to pull from Polymarket + Kalshi.</p>
      ) : null}

      {markets.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              <th>Question</th>
              <th>Category</th>
              <th style={{ textAlign: "right" }}>Liquidity</th>
              <th>Closes</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((market) => (
              <tr key={market.id}>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{market.platform}</td>
                <td>
                  <Link href={`/markets/${market.id}`}>{market.question_text}</Link>
                </td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{market.category}</td>
                <td style={{ textAlign: "right", color: "var(--muted)" }}>
                  {formatLiquidity(market.liquidity)}
                </td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>
                  {new Date(market.close_time).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
