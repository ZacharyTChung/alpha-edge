"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

export function ReclassifyButton({ marketId }: { marketId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);

  const onClick = async () => {
    setBusy(true);
    setSummary(null);
    try {
      const r = await api.reclassifyMarket(marketId);
      if (r.detail) {
        setSummary(`error: ${r.detail}`);
      } else {
        setSummary(
          `kept ${r.kept} of ${r.reclassified}, dropped ${r.dropped} as off-topic. ` +
            `new signal: ${r.new_signal.tier} (edge ${(r.new_signal.edge * 100).toFixed(1)}pp)`
        );
        router.refresh();
      }
    } catch (e) {
      setSummary(`error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      <button
        onClick={onClick}
        disabled={busy}
        title="Re-run Claude on every existing sentiment event for this market and drop off-topic ones"
        style={{
          background: "transparent",
          color: "var(--accent)",
          border: "1px solid var(--accent)",
          padding: "6px 14px",
          fontFamily: "inherit",
          fontSize: 12,
          cursor: busy ? "wait" : "pointer",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {busy ? "Reclassifying…" : "Reclassify with Claude"}
      </button>
      {summary ? (
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{summary}</span>
      ) : null}
    </div>
  );
}
