import type { DecisionInfo } from "@/lib/api";

const COLORS: Record<DecisionInfo["decision"], string> = {
  BET_OVER: "var(--accent)",
  BET_UNDER: "var(--bad)",
  NO_BET: "var(--muted)",
};

const RISK_COLORS: Record<DecisionInfo["risk_level"], string> = {
  LOW: "var(--accent)",
  MEDIUM: "var(--warn)",
  HIGH: "var(--bad)",
};

/**
 * Top-of-page banner: BET OVER / BET UNDER / NO BET decision per v2.0
 * thresholds (|edge| ≥ 5pp AND confidence ≥ 7), with the confidence
 * breakdown alongside.
 */
export function DecisionCard({ decision }: { decision: DecisionInfo }) {
  const label = decision.decision === "NO_BET" ? "NO BET" : decision.decision.replace("_", " ");
  return (
    <div
      style={{
        marginTop: 16,
        marginBottom: 16,
        border: `1px solid ${COLORS[decision.decision]}`,
        padding: "16px 20px",
        display: "flex",
        gap: 24,
        alignItems: "stretch",
        flexWrap: "wrap",
      }}
    >
      <div style={{ flex: "0 0 auto" }}>
        <div
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--muted)",
            marginBottom: 4,
          }}
        >
          decision
        </div>
        <div
          style={{
            fontSize: 22,
            color: COLORS[decision.decision],
            fontWeight: 500,
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--muted)",
            marginTop: 8,
          }}
        >
          risk
        </div>
        <div style={{ color: RISK_COLORS[decision.risk_level], fontSize: 14 }}>
          {decision.risk_level}
        </div>
      </div>

      <div
        style={{
          flex: "0 0 auto",
          paddingLeft: 24,
          borderLeft: "1px solid var(--border)",
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
          confidence
        </div>
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
        <div
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--muted)",
            marginBottom: 4,
          }}
        >
          reasoning
        </div>
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
  );
}
