import { api, type DashboardStats } from "@/lib/api";

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

  const cell = (label: string, value: string | number, color?: string) => (
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
        }}
      >
        {label}
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
      {cell("markets tracked", `${stats.open_market_count} / ${stats.market_count}`)}
      {cell("strong signals", tiers.STRONG, "var(--accent)")}
      {cell("lean", tiers.LEAN)}
      {cell("fade", tiers.FADE, "var(--bad)")}
      {cell("sentiment events", stats.sentiment_count.toLocaleString())}
      {cell("last signal", lastSeen)}
    </div>
  );
}
