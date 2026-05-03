import { api, type EdgeReportItem } from "@/lib/api";
import { SignalGlossary } from "@/app/components/signal-glossary";
import { EdgeTable } from "./edge-table";

export const dynamic = "force-dynamic";

export default async function EdgePage() {
  let items: EdgeReportItem[] = [];
  let error: string | null = null;
  try {
    items = await api.getEdgeReport(0.02);
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <section>
      <h2>Edge Report</h2>
      <p style={{ color: "var(--muted)" }}>
        Open markets sorted by absolute edge. Each row is the latest signal per market.
      </p>

      <div
        style={{
          display: "flex",
          gap: 24,
          marginBottom: 16,
          flexWrap: "wrap",
          fontSize: 12,
        }}
      >
        <TierLegend label="STRONG" desc="≥ +10pp · model strongly favors YES" cssClass="tier-STRONG" />
        <TierLegend label="LEAN" desc="+4pp to +10pp · model leans YES" cssClass="tier-LEAN" />
        <TierLegend label="NONE" desc="within ±4pp · agrees with market" cssClass="tier-NONE" />
        <TierLegend label="FADE" desc="≤ −10pp · model strongly favors NO" cssClass="tier-FADE" />
      </div>

      {error ? <p>API unreachable: {error}</p> : null}
      {!error ? <EdgeTable items={items} /> : null}

      <SignalGlossary />
    </section>
  );
}

function TierLegend({ label, desc, cssClass }: { label: string; desc: string; cssClass: string }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
      <span className={cssClass} style={{ fontWeight: "normal" }}>
        {label}
      </span>
      <span style={{ color: "var(--muted)" }}>{desc}</span>
    </div>
  );
}
