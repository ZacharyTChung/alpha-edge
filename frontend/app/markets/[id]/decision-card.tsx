import type { DecisionInfo } from "@/lib/api";

const DECISION_COLORS: Record<DecisionInfo["decision"], string> = {
  BUY_YES: "var(--accent)",
  BUY_NO: "var(--bad)",
  NO_BET: "var(--muted)",
};

const FORECAST_COLORS: Record<DecisionInfo["outcome_forecast"], string> = {
  YES: "var(--accent)",
  NO: "var(--bad)",
  UNCERTAIN: "var(--muted)",
};

const RISK_COLORS: Record<DecisionInfo["risk_level"], string> = {
  LOW: "var(--accent)",
  MEDIUM: "var(--warn)",
  HIGH: "var(--bad)",
};

/**
 * Three pieces of independent information rendered together:
 *
 * 1. **Outcome Forecast** — what the model thinks will happen (YES / NO /
 *    UNCERTAIN). Shown regardless of bet recommendation.
 * 2. **Bet Decision** — BUY YES / BUY NO / NO BET, derived from edge +
 *    confidence + saturation. "Buy YES" = the model thinks the YES outcome is
 *    underpriced; "Buy NO" = overpriced. Saturated markets always say NO BET.
 * 3. **Confidence + Reasoning** — the explanation.
 *
 * The forecast/decision separation fixes the most common UX confusion:
 * "Why doesn't it bet YES when YES is obviously going to happen?" — because
 * a 99% market price means a 1% payout, even on a sure thing.
 */
export function DecisionCard({ decision }: { decision: DecisionInfo }) {
  const betLabel =
    decision.decision === "NO_BET" ? "NO BET" : decision.decision.replace("_", " ");
  const forecastLabel =
    decision.outcome_forecast === "YES"
      ? "YES likely"
      : decision.outcome_forecast === "NO"
      ? "NO likely"
      : "uncertain";
  const forecastPct = (decision.outcome_forecast_pct * 100).toFixed(1);

  return (
    <div
      style={{
        marginTop: 16,
        marginBottom: 16,
        border: `1px solid ${DECISION_COLORS[decision.decision]}`,
        padding: "16px 20px",
      }}
    >
      <div style={{ display: "flex", gap: 24, alignItems: "stretch", flexWrap: "wrap" }}>
        <div style={{ flex: "0 0 auto" }}>
          <Label>outcome forecast</Label>
          <div style={{ fontSize: 20, color: FORECAST_COLORS[decision.outcome_forecast] }}>
            {forecastLabel}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            model: {forecastPct}%
          </div>
        </div>

        <div
          style={{
            flex: "0 0 auto",
            paddingLeft: 24,
            borderLeft: "1px solid var(--border)",
          }}
        >
          <Label>bet decision</Label>
          <div
            style={{
              fontSize: 22,
              color: DECISION_COLORS[decision.decision],
              fontWeight: 500,
              letterSpacing: "0.05em",
            }}
          >
            {betLabel}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            risk:{" "}
            <span style={{ color: RISK_COLORS[decision.risk_level] }}>{decision.risk_level}</span>
          </div>
        </div>

        <div
          style={{
            flex: "0 0 auto",
            paddingLeft: 24,
            borderLeft: "1px solid var(--border)",
          }}
        >
          <Label>confidence</Label>
          <div style={{ fontSize: 22 }}>
            {decision.confidence}
            <span style={{ color: "var(--muted)", fontSize: 14 }}>/10</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
            {decision.confidence >= decision.confidence_floor
              ? "above bet floor"
              : `below bet floor (need ${decision.confidence_floor})`}
          </div>
        </div>

        <div
          style={{
            flex: 1,
            paddingLeft: 24,
            borderLeft: "1px solid var(--border)",
            minWidth: 280,
          }}
        >
          <Label>reasoning</Label>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>{decision.reasoning}</div>
          {decision.deductions.length > 0 || decision.bonuses.length > 0 ? (
            <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
              {decision.deductions.map((d) => (
                <div key={d}>− {d}</div>
              ))}
              {decision.bonuses.map((b) => (
                <div key={b} style={{ color: "var(--accent)" }}>
                  + {b}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {decision.saturated_market ? (
        <div
          style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: "1px solid var(--border)",
            color: "var(--warn)",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          ⚠️ <strong>Saturated market</strong> — the market price is at an extreme
          (≥95% or ≤5%), so the available payout per dollar risked is too small to make
          any bet actionable. Alpha Edge finds <em>mispriced</em> markets, not predictions.
          A near-certain outcome already priced as near-certain has no edge to capture.
        </div>
      ) : null}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: "var(--muted)",
        marginBottom: 4,
      }}
    >
      {children}
    </div>
  );
}
