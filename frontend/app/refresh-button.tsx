"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

export function RefreshButton() {
  const router = useRouter();
  const [busy, setBusy] = useState<"none" | "full" | "priority">("none");
  const [summary, setSummary] = useState<string | null>(null);

  const run = async (priority: boolean) => {
    setBusy(priority ? "priority" : "full");
    setSummary(null);
    try {
      const r = await api.refresh(priority);
      const llm = r.llm_enabled ? `llm=${r.llm_classifications}` : "llm=off";
      setSummary(
        `poly=${r.polymarket_markets} kalshi=${r.kalshi_markets} sentiment=${r.sentiment_events} signals=${r.signals_written} ${llm}` +
          (r.errors?.length ? ` errors=${r.errors.length}` : "")
      );
      router.refresh();
    } catch (e) {
      setSummary(`error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy("none");
    }
  };

  const baseStyle: React.CSSProperties = {
    background: "transparent",
    color: "var(--accent)",
    border: "1px solid var(--accent)",
    padding: "6px 14px",
    fontFamily: "inherit",
    fontSize: 12,
    cursor: busy !== "none" ? "wait" : "pointer",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  };

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      {summary ? <span style={{ color: "var(--muted)", fontSize: 12 }}>{summary}</span> : null}
      <button
        onClick={() => run(true)}
        disabled={busy !== "none"}
        title="Sports markets only, ≥$5k liquidity, sub-30s"
        style={{ ...baseStyle, color: "var(--fg)", borderColor: "var(--border)" }}
      >
        {busy === "priority" ? "Priority…" : "Priority"}
      </button>
      <button onClick={() => run(false)} disabled={busy !== "none"} style={baseStyle}>
        {busy === "full" ? "Full refresh…" : "Full refresh"}
      </button>
    </div>
  );
}
