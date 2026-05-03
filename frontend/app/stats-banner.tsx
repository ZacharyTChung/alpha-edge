import { api, type DashboardStats } from "@/lib/api";
import { InfoTip } from "./components/info-tip";

export async function StatsBanner() {
  let stats: DashboardStats | null = null;
  try {
    stats = await api.getStats();
  } catch {
    return null;
  }

  const tiers = stats.by_tier;
  const lastSeen = stats.last_signal_at
    ? new Date(stats.last_signal_at).toLocaleString()
    : "never";

  const cell = (label: string, value: string | number, color?: string, tip?: React.ReactNode) => (
    <div
      style={{
        flex: 1,
        padding: "12px 16px",
        borderRight: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
          marginBottom: 4,
          display: "flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip ? <InfoTip>{tip}</InfoTip> : null}
      </div>
      <div style={{ fontSize: 18, color: color ?? "var(--fg)" }}>{value}</div>
    </div>
  );

  return (
    <div
      style={{
        display: "flex",
        border: "1px solid var(--border)",
        marginBottom: 24,
        background: "rgba(255,255,255,0.02)",
      }}
    >
      {cell(
        "markets tracked",
        `${stats.open_market_count} / ${stats.market_count}`,
        undefined,
        "Open markets / total markets ever ingested. Once a market resolves we stop refreshing it but keep it for calibration."
      )}
      {cell(
        "strong signals",
        tiers.STRONG,
        "var(--accent)",
        "Markets where our model probability is ≥ 10pp above the YES market price. Highest-conviction bullish bets."
      )}
      {cell(
        "lean",
        tiers.LEAN,
        undefined,
        "Markets with edge between +4pp and +10pp — directional but lower conviction than STRONG."
      )}
      {cell(
        "fade",
        tiers.FADE,
        "var(--bad)",
        "Markets where the model is ≥ 10pp below the YES price — sell YES or buy NO."
      )}
      {cell(
        "sentiment events",
        stats.sentiment_count.toLocaleString(),
        undefined,
        "Total text snippets ingested across news, Reddit, Bluesky, X, etc. Each market's sentiment evidence shows the most relevant subset."
      )}
      {cell(
        "last signal",
        lastSeen,
        undefined,
        "When the most recent signal was generated. Click Priority or Full refresh to update."
      )}
    </div>
  );
}
