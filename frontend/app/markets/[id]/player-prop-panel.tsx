import type { PlayerPropInfo } from "@/lib/api";

const fmt = (n: number, dp = 2) => n.toFixed(dp);
const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`;
const signed = (n: number, dp = 2) => (n >= 0 ? `+${fmt(n, dp)}` : fmt(n, dp));

/**
 * v2.0 player-prop projection panel — shows the structured statistical model
 * (weighted-median base + adjustments → projected mean → z-score → prob_over).
 * Only rendered when the market is detected as a player prop.
 */
export function PlayerPropPanel({ prop }: { prop: PlayerPropInfo }) {
  if (prop.error) {
    return (
      <section
        style={{
          marginTop: 24,
          border: "1px solid var(--border)",
          background: "rgba(255,255,255,0.02)",
          padding: 20,
        }}
      >
        <h3 style={{ marginTop: 0, marginBottom: 4 }}>Player-Prop Projection (v2.0)</h3>
        <p style={{ color: "var(--muted)", fontSize: 12 }}>
          Detected as a {prop.parsed.prop_type} prop for {prop.parsed.player_name ?? "unknown player"}{" "}
          {prop.parsed.side} {prop.parsed.line}, but no projection available: {prop.error}
        </p>
      </section>
    );
  }

  if (prop.projected_mean === undefined) return null;

  const computedAdjustments = (prop.adjustments ?? []).filter(
    (a) => a.value !== 0 || a.note !== "data not yet ingested"
  );
  const missingAdjustments = (prop.adjustments ?? []).filter(
    (a) => a.value === 0 && a.note === "data not yet ingested"
  );

  return (
    <section
      style={{
        marginTop: 24,
        border: "1px solid var(--accent)",
        background: "rgba(74,222,128,0.04)",
        padding: 20,
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 4 }}>Player-Prop Projection</h3>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 0 }}>
        Structured statistical model per Alpha Edge v2.0 spec. Used in addition to the
        sentiment-based posterior above for player-prop markets specifically.
      </p>

      <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginTop: 12 }}>
        <Stat label="Player" value={prop.parsed.player_name ?? "—"} />
        <Stat label="Prop" value={`${prop.parsed.prop_type ?? "—"} ${prop.parsed.side} ${prop.parsed.line}`} />
        <Stat label="Games used" value={`${prop.n_games_used ?? "—"}`} />
        <Stat label="SD source" value={prop.sd_source ?? "—"} />
      </div>

      <h4 style={{ marginTop: 18, marginBottom: 4, fontWeight: "normal", fontSize: 13 }}>
        Projection breakdown
      </h4>
      <table style={{ marginTop: 4, fontSize: 12 }}>
        <tbody>
          <tr>
            <td style={{ paddingRight: 16 }}>
              <code>Base = 0.30·season_med + 0.30·last20_med + 0.25·last10_med + 0.15·last5_med</code>
            </td>
            <td style={{ textAlign: "right" }}>
              <strong>{fmt(prop.base_projection ?? 0)}</strong>
            </td>
          </tr>
          {computedAdjustments.map((a) => (
            <tr key={a.name}>
              <td style={{ paddingRight: 16 }}>
                <code>+ {a.name}</code>{" "}
                <span style={{ color: "var(--muted)" }}>({a.note})</span>
              </td>
              <td
                style={{
                  textAlign: "right",
                  color: a.value > 0 ? "var(--accent)" : a.value < 0 ? "var(--bad)" : "var(--muted)",
                }}
              >
                {signed(a.value)}
              </td>
            </tr>
          ))}
          <tr>
            <td
              style={{
                paddingTop: 8,
                paddingRight: 16,
                borderTop: "1px solid var(--border)",
              }}
            >
              <strong>Projected mean</strong>
            </td>
            <td style={{ textAlign: "right", paddingTop: 8, borderTop: "1px solid var(--border)" }}>
              <strong>{fmt(prop.projected_mean)}</strong>
            </td>
          </tr>
        </tbody>
      </table>

      {missingAdjustments.length > 0 ? (
        <p style={{ color: "var(--warn)", fontSize: 11, marginTop: 8 }}>
          ⚠️ Skipped (data not yet ingested): {missingAdjustments.map((a) => a.name).join(", ")} —
          full v2.0 spec calls for these.
        </p>
      ) : null}

      <h4 style={{ marginTop: 18, marginBottom: 4, fontWeight: "normal", fontSize: 13 }}>
        Probability via z-score
      </h4>
      <div style={{ fontFamily: "monospace", fontSize: 12, color: "var(--fg)" }}>
        <div>
          z = (line − μ) / σ = ({fmt(prop.parsed.line ?? 0)} − {fmt(prop.projected_mean)}) /{" "}
          {fmt(prop.adjusted_sd ?? 0)} = <strong>{signed(prop.z_score ?? 0, 3)}</strong>
        </div>
        <div style={{ marginTop: 4 }}>
          P(over {prop.parsed.line}) = 1 − Φ(z) ={" "}
          <strong style={{ color: "var(--accent)" }}>{pct(prop.model_prob_over ?? 0, 2)}</strong>
        </div>
        <div>
          P(under {prop.parsed.line}) = Φ(z) ={" "}
          <strong>{pct(prop.model_prob_under ?? 0, 2)}</strong>
        </div>
      </div>

      {prop.flags && Object.values(prop.flags).some(Boolean) ? (
        <div style={{ marginTop: 12, fontSize: 11 }}>
          <span style={{ color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            flags:
          </span>{" "}
          {Object.entries(prop.flags)
            .filter(([, v]) => v)
            .map(([k]) => (
              <span
                key={k}
                style={{
                  marginLeft: 8,
                  padding: "2px 8px",
                  border: "1px solid var(--warn)",
                  color: "var(--warn)",
                  borderRadius: 2,
                }}
              >
                {k}
              </span>
            ))}
        </div>
      ) : null}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 14 }}>{value}</div>
    </div>
  );
}
