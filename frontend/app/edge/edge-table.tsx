"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { EdgeReportItem } from "@/lib/api";

type Tier = "ALL" | "STRONG" | "LEAN" | "FADE";
type Cat = "ALL" | "sports" | "politics" | "finance";
type Plat = "ALL" | "kalshi" | "polymarket";

export function EdgeTable({ items }: { items: EdgeReportItem[] }) {
  const [tier, setTier] = useState<Tier>("ALL");
  const [cat, setCat] = useState<Cat>("ALL");
  const [plat, setPlat] = useState<Plat>("ALL");

  const filtered = useMemo(() => {
    return items.filter((i) => {
      if (tier !== "ALL" && i.signal_tier !== tier) return false;
      if (cat !== "ALL" && i.category !== cat) return false;
      if (plat !== "ALL" && i.platform !== plat) return false;
      return true;
    });
  }, [items, tier, cat, plat]);

  const tiers = ["ALL", "STRONG", "LEAN", "FADE"] as const;
  const cats = ["ALL", "sports", "politics", "finance"] as const;
  const plats = ["ALL", "kalshi", "polymarket"] as const;

  return (
    <>
      <div
        style={{
          display: "flex",
          gap: 16,
          marginBottom: 16,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <FilterGroup label="tier" value={tier} options={tiers} onChange={(v) => setTier(v as Tier)} />
        <FilterGroup label="category" value={cat} options={cats} onChange={(v) => setCat(v as Cat)} />
        <FilterGroup label="platform" value={plat} options={plats} onChange={(v) => setPlat(v as Plat)} />
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          {filtered.length} of {items.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>No edges match the current filters.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>Plat</th>
              <th>Cat</th>
              <th style={{ textAlign: "right" }}>Model</th>
              <th style={{ textAlign: "right" }}>Price</th>
              <th style={{ textAlign: "right" }}>Edge</th>
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.market_id + item.signal_tier}>
                <td>
                  <Link href={`/markets/${item.market_id}`}>{item.question_text}</Link>
                </td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{item.platform ?? "—"}</td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{item.category ?? "—"}</td>
                <td style={{ textAlign: "right" }}>{(item.model_probability * 100).toFixed(1)}%</td>
                <td style={{ textAlign: "right" }}>{(item.market_price * 100).toFixed(1)}%</td>
                <td
                  style={{
                    textAlign: "right",
                    color: item.edge > 0 ? "var(--accent)" : "var(--bad)",
                  }}
                >
                  {item.edge >= 0 ? "+" : ""}
                  {(item.edge * 100).toFixed(2)}
                </td>
                <td className={`tier-${item.signal_tier}`}>{item.signal_tier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function FilterGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <span style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase" }}>
        {label}
      </span>
      <div style={{ display: "flex", border: "1px solid var(--border)" }}>
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            style={{
              background: value === opt ? "var(--accent)" : "transparent",
              color: value === opt ? "var(--bg)" : "var(--muted)",
              border: "none",
              padding: "4px 10px",
              fontFamily: "inherit",
              fontSize: 11,
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}
