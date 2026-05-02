"use client";

interface Series {
  values: number[];
  color: string;
  label: string;
}

export function PriceSparkline({
  series,
  width = 320,
  height = 60,
}: {
  series: Series[];
  width?: number;
  height?: number;
}) {
  const all = series.flatMap((s) => s.values);
  if (all.length === 0) return null;
  const min = Math.min(...all, 0);
  const max = Math.max(...all, 1);
  const span = Math.max(0.001, max - min);

  const lineFor = (vals: number[]) => {
    if (vals.length === 0) return "";
    const stepX = vals.length > 1 ? width / (vals.length - 1) : 0;
    return vals
      .map((v, i) => {
        const x = i * stepX;
        const y = height - ((v - min) / span) * (height - 4) - 2;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  return (
    <div>
      <svg width={width} height={height} style={{ display: "block" }}>
        <line x1={0} y1={height - 2} x2={width} y2={height - 2} stroke="var(--border)" />
        {series.map((s) => (
          <path key={s.label} d={lineFor(s.values)} stroke={s.color} strokeWidth={1.5} fill="none" />
        ))}
      </svg>
      <div style={{ display: "flex", gap: 12, fontSize: 11, marginTop: 4 }}>
        {series.map((s) => (
          <span key={s.label} style={{ color: s.color }}>
            ● {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
