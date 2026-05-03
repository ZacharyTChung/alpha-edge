import type { MarketCalculation } from "@/lib/api";

const fmt = (n: number, dp = 4) => n.toFixed(dp);
const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`;
const pp = (n: number, dp = 2) => `${(n * 100).toFixed(dp)}pp`;
const signed = (n: number, dp = 4) => (n >= 0 ? `+${fmt(n, dp)}` : fmt(n, dp));

/**
 * Server-rendered calculation breakdown panel — every number that goes into
 * the model's posterior, in the order they're applied. Inspect the math.
 */
export function CalculationPanel({ calc }: { calc: MarketCalculation }) {
  const { prior, evidence, posterior, edge, betting } = calc;

  return (
    <section
      style={{
        marginTop: 24,
        border: "1px solid var(--border)",
        background: "rgba(255,255,255,0.02)",
        padding: 20,
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 4 }}>Calculation Breakdown</h3>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 0 }}>
        Every input, intermediate value, and coefficient that produced the posterior. Read top to
        bottom — math is auditable.
      </p>

      <Row label="1. Prior (from market price)">
        <Code>p_market = {fmt(prior.p_market, 4)}</Code>
        <Code>
          ℓ₀ = log(p / (1 − p)) = log({fmt(prior.p_market, 4)} / {fmt(1 - prior.p_market, 4)}) ={" "}
          <strong>{signed(prior.log_odds)}</strong>
        </Code>
      </Row>

      <Row label={`2. Evidence (${evidence.n_events} events, grouped by source)`}>
        <table style={{ marginTop: 4, fontSize: 12 }}>
          <thead>
            <tr>
              <th>Source</th>
              <th style={{ textAlign: "right" }}>n</th>
              <th style={{ textAlign: "right" }}>β</th>
              <th style={{ textAlign: "right" }}>x̄ (signed score)</th>
              <th style={{ textAlign: "right" }}>raw log-LR</th>
              <th style={{ textAlign: "right" }}>capped to ±0.8</th>
              <th style={{ textAlign: "right" }}>Var contrib</th>
            </tr>
          </thead>
          <tbody>
            {evidence.per_source.map((c) => (
              <tr key={c.source_key}>
                <td>
                  <code>{c.source_key}</code>
                </td>
                <td style={{ textAlign: "right" }}>{c.n_events}</td>
                <td style={{ textAlign: "right" }}>{fmt(c.beta_coefficient, 2)}</td>
                <td
                  style={{
                    textAlign: "right",
                    color:
                      c.avg_signed_score > 0
                        ? "var(--accent)"
                        : c.avg_signed_score < 0
                        ? "var(--bad)"
                        : "var(--muted)",
                  }}
                >
                  {signed(c.avg_signed_score, 3)}
                </td>
                <td style={{ textAlign: "right", color: "var(--muted)" }}>
                  {signed(c.raw_log_LR, 4)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    color: c.was_capped ? "var(--warn)" : "var(--fg)",
                  }}
                  title={c.was_capped ? "raw log-LR exceeded ±0.8 — clipped" : ""}
                >
                  {signed(c.capped_log_LR, 4)} {c.was_capped ? "✂" : ""}
                </td>
                <td style={{ textAlign: "right", color: "var(--muted)" }}>
                  {fmt(c.variance_contribution, 4)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4} style={{ color: "var(--muted)", paddingTop: 8 }}>
                Σ over sources →
              </td>
              <td colSpan={2} style={{ textAlign: "right", paddingTop: 8 }}>
                <strong>Δℓ = {signed(evidence.delta_log_odds)}</strong>
              </td>
              <td style={{ textAlign: "right", paddingTop: 8, color: "var(--muted)" }}>
                σ² total
              </td>
            </tr>
          </tfoot>
        </table>
        <p style={{ color: "var(--muted)", fontSize: 11, marginTop: 8 }}>
          For each event: x = polarity × relevance × confidence. Per-source contribution is
          Σ β·x, clipped to ±0.8 to bound any single source's influence (independence-violation
          correction).
        </p>
      </Row>

      <Row label="3. Posterior log-odds">
        <Code>
          ℓ_post = ℓ₀ + Δℓ = {signed(prior.log_odds)} + {signed(evidence.delta_log_odds)} ={" "}
          <strong>{signed(posterior.log_odds)}</strong>
        </Code>
        <Code>
          p_post = σ(ℓ_post) = 1 / (1 + e^−({signed(posterior.log_odds)})) ={" "}
          <strong style={{ color: "var(--accent)" }}>{pct(posterior.probability, 2)}</strong>
        </Code>
      </Row>

      <Row label="4. Credible interval (95%)">
        <Code>
          σ = √Var(ℓ_post) = √{fmt(posterior.variance_log_odds, 4)} ={" "}
          {fmt(posterior.sigma_log_odds, 4)}
        </Code>
        <Code>
          ℓ_post ± 1.96·σ ∈ [{signed(posterior.log_odds - 1.96 * posterior.sigma_log_odds, 3)},{" "}
          {signed(posterior.log_odds + 1.96 * posterior.sigma_log_odds, 3)}]
        </Code>
        <Code>
          → 95% CI on probability: [<strong>{pct(posterior.ci_95_low, 1)}</strong>,{" "}
          <strong>{pct(posterior.ci_95_high, 1)}</strong>]
        </Code>
      </Row>

      <Row label="5. Edge & tier">
        <Code>
          edge = p_post − p_market = {pct(posterior.probability, 2)} − {pct(prior.p_market, 2)} ={" "}
          <strong style={{ color: edge.edge > 0 ? "var(--accent)" : "var(--bad)" }}>
            {edge.edge > 0 ? "+" : ""}
            {pp(edge.edge, 2)}
          </strong>{" "}
          → tier <span className={`tier-${edge.tier}`}>{edge.tier}</span>
        </Code>
      </Row>

      <Row label="6. Quarter-Kelly bet sizing">
        <Code>b = 1/p_market − 1 = {fmt(1 / prior.p_market - 1, 3)} (decimal odds payoff)</Code>
        <Code>
          f* = (b·p − q) / b = ({fmt(1 / prior.p_market - 1, 3)} ·{" "}
          {fmt(posterior.probability, 4)} − {fmt(1 - posterior.probability, 4)}) /{" "}
          {fmt(1 / prior.p_market - 1, 3)} = {fmt(betting.full_kelly_fraction, 4)}
        </Code>
        <Code>
          recommended (¼ Kelly) ={" "}
          <strong style={{ color: "var(--accent)" }}>
            {betting.quarter_kelly_pct_bankroll.toFixed(2)}%
          </strong>{" "}
          of bankroll
        </Code>
      </Row>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: 12,
        marginBottom: 2,
        color: "var(--fg)",
      }}
    >
      {children}
    </div>
  );
}
