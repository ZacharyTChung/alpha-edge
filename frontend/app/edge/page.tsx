import { api, type EdgeReportItem } from "@/lib/api";
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
        Open markets sorted by absolute edge. Strong tier ≥ 10pp gap, Lean ≥ 4pp, Fade ≤ −10pp.
        Filter by tier, category, or platform below.
      </p>
      {error ? <p>API unreachable: {error}</p> : null}
      {!error ? <EdgeTable items={items} /> : null}
    </section>
  );
}
