"use client";

import { useState } from "react";

import type { Signal } from "@/lib/api";

interface Props {
  signals: Signal[];
  width?: number;
  height?: number;
}

/**
 * Two-line plot of model probability vs market price over signal-history time.
 *
 * - Time-based X-axis (positions reflect actual elapsed time, not index)
 * - Percent Y-axis (0–100%)
 * - 50% reference baseline (the coin-flip line)
 * - Shaded edge zone between model and market — green when model > market, red otherwise
 * - Latest-value chips at the right edge with the current values
 * - Hover crosshair shows the (model, market, edge) at that timestamp
 */
export function SignalChart({ signals, width = 720, height = 240 }: Props) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  // Signals come in newest-first; reverse for chronological X-axis.
  const ordered = [...signals].reverse();
  if (ordered.length < 2) return null;

  const padding = { top: 16, right: 96, bottom: 30, left: 44 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const times = ordered.map((s) => new Date(s.generated_at).getTime());
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const tSpan = Math.max(1, tMax - tMin);

  const xFor = (t: number) => padding.left + ((t - tMin) / tSpan) * innerW;
  const yFor = (p: number) => padding.top + (1 - p) * innerH;

  const modelPath = ordered
    .map((s, i) => `${i === 0 ? "M" : "L"}${xFor(times[i]).toFixed(1)},${yFor(s.model_probability).toFixed(1)}`)
    .join(" ");
  const marketPath = ordered
    .map((s, i) => `${i === 0 ? "M" : "L"}${xFor(times[i]).toFixed(1)},${yFor(s.market_price).toFixed(1)}`)
    .join(" ");

  // Build the edge-zone polygon: model line forward, market line reverse, with
  // a fill color tied to the sign of the latest edge.
  const latestEdge = ordered[ordered.length - 1].edge;
  const edgeColor = latestEdge >= 0 ? "rgba(74, 222, 128, 0.18)" : "rgba(239, 68, 68, 0.18)";
  const polyPoints = [
    ...ordered.map((s, i) => `${xFor(times[i]).toFixed(1)},${yFor(s.model_probability).toFixed(1)}`),
    ...ordered
      .slice()
      .reverse()
      .map((s, i) => {
        const idx = ordered.length - 1 - i;
        return `${xFor(times[idx]).toFixed(1)},${yFor(s.market_price).toFixed(1)}`;
      }),
  ].join(" ");

  const yTicks = [0, 0.25, 0.5, 0.75, 1];
  const xTickIdxs =
    ordered.length <= 6
      ? ordered.map((_, i) => i)
      : [0, Math.floor(ordered.length / 3), Math.floor((ordered.length * 2) / 3), ordered.length - 1];

  const fmtPct = (p: number) => `${(p * 100).toFixed(0)}%`;
  const fmtTime = (t: number) =>
    new Date(t).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) +
    "  " +
    new Date(t).toLocaleDateString([], { month: "short", day: "numeric" });

  const last = ordered[ordered.length - 1];

  return (
    <div style={{ marginTop: 8 }}>
      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          marginBottom: 8,
          fontSize: 12,
          color: "var(--muted)",
        }}
      >
        <span style={{ color: "var(--accent)" }}>● model probability</span>
        <span style={{ color: "var(--fg)" }}>● market price</span>
        <span>shaded zone = current edge ({latestEdge >= 0 ? "model favors YES" : "model favors NO"})</span>
      </div>
      <svg
        width={width}
        height={height}
        style={{ display: "block", maxWidth: "100%" }}
        onMouseLeave={() => setHoverIdx(null)}
        onMouseMove={(e) => {
          const rect = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
          const px = e.clientX - rect.left;
          // Find nearest data index by X distance
          let best = 0;
          let bestD = Infinity;
          for (let i = 0; i < ordered.length; i++) {
            const d = Math.abs(xFor(times[i]) - px);
            if (d < bestD) {
              bestD = d;
              best = i;
            }
          }
          setHoverIdx(best);
        }}
      >
        {/* Y gridlines + labels */}
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line
              x1={padding.left}
              y1={yFor(t)}
              x2={padding.left + innerW}
              y2={yFor(t)}
              stroke={t === 0.5 ? "var(--muted)" : "var(--border)"}
              strokeDasharray={t === 0.5 ? "4 4" : "none"}
              strokeWidth={1}
              opacity={t === 0.5 ? 0.6 : 0.5}
            />
            <text
              x={padding.left - 8}
              y={yFor(t) + 3}
              fontSize={10}
              fill="var(--muted)"
              textAnchor="end"
            >
              {fmtPct(t)}
            </text>
          </g>
        ))}

        {/* X tick labels */}
        {xTickIdxs.map((i) => (
          <text
            key={`x${i}`}
            x={xFor(times[i])}
            y={height - 8}
            fontSize={10}
            fill="var(--muted)"
            textAnchor="middle"
          >
            {new Date(times[i]).toLocaleString([], { month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" })}
          </text>
        ))}

        {/* Edge fill */}
        <polygon points={polyPoints} fill={edgeColor} stroke="none" />

        {/* Series lines */}
        <path d={marketPath} stroke="var(--fg)" strokeWidth={1.5} fill="none" opacity={0.85} />
        <path d={modelPath} stroke="var(--accent)" strokeWidth={2} fill="none" />

        {/* Endpoint markers */}
        <circle cx={xFor(times[ordered.length - 1])} cy={yFor(last.model_probability)} r={3.5} fill="var(--accent)" />
        <circle cx={xFor(times[ordered.length - 1])} cy={yFor(last.market_price)} r={3.5} fill="var(--fg)" />

        {/* Right-edge value chips */}
        <g transform={`translate(${padding.left + innerW + 6}, 0)`}>
          <text x={0} y={yFor(last.model_probability) + 3} fontSize={11} fill="var(--accent)">
            {fmtPct(last.model_probability)}
          </text>
          <text x={0} y={yFor(last.market_price) + 3} fontSize={11} fill="var(--fg)">
            {fmtPct(last.market_price)}
          </text>
        </g>

        {/* Hover crosshair + readout */}
        {hoverIdx !== null ? (
          <g>
            <line
              x1={xFor(times[hoverIdx])}
              x2={xFor(times[hoverIdx])}
              y1={padding.top}
              y2={padding.top + innerH}
              stroke="var(--muted)"
              strokeDasharray="2 3"
              opacity={0.7}
            />
            <circle
              cx={xFor(times[hoverIdx])}
              cy={yFor(ordered[hoverIdx].model_probability)}
              r={3}
              fill="var(--accent)"
            />
            <circle
              cx={xFor(times[hoverIdx])}
              cy={yFor(ordered[hoverIdx].market_price)}
              r={3}
              fill="var(--fg)"
            />
          </g>
        ) : null}
      </svg>

      {hoverIdx !== null ? (
        <div
          style={{
            marginTop: 6,
            fontSize: 12,
            color: "var(--muted)",
            display: "flex",
            gap: 18,
            flexWrap: "wrap",
          }}
        >
          <span>{fmtTime(times[hoverIdx])}</span>
          <span style={{ color: "var(--accent)" }}>
            model {fmtPct(ordered[hoverIdx].model_probability)}
          </span>
          <span style={{ color: "var(--fg)" }}>market {fmtPct(ordered[hoverIdx].market_price)}</span>
          <span
            style={{
              color: ordered[hoverIdx].edge >= 0 ? "var(--accent)" : "var(--bad)",
            }}
          >
            edge {ordered[hoverIdx].edge >= 0 ? "+" : ""}
            {(ordered[hoverIdx].edge * 100).toFixed(2)}pp
          </span>
          <span className={`tier-${ordered[hoverIdx].signal_tier}`}>
            tier {ordered[hoverIdx].signal_tier}
          </span>
        </div>
      ) : (
        <div style={{ marginTop: 6, fontSize: 11, color: "var(--muted)" }}>
          hover for point-in-time values · {ordered.length} signals over{" "}
          {((tMax - tMin) / 3600000).toFixed(1)}h
        </div>
      )}
    </div>
  );
}
