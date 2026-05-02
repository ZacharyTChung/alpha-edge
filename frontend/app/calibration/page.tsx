import { api } from "@/lib/api";

interface Bucket {
  bucket_low: number;
  bucket_high: number;
  predicted_mean: number;
  actual_rate: number;
  count: number;
}

interface Report {
  brier_score: number | null;
  log_loss: number | null;
  buckets: Bucket[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export default async function CalibrationPage() {
  let report: Report | null = null;
  let error: string | null = null;
  try {
    const response = await fetch(`${API_BASE}/calibration`, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    report = await response.json();
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  let closing: Awaited<ReturnType<typeof api.getClosingLine>> | null = null;
  try {
    closing = await api.getClosingLine();
  } catch {
    closing = null;
  }

  return (
    <section>
      <h2>Calibration</h2>
      <p style={{ color: "var(--muted)" }}>
        Reliability diagram: predicted probability bucket vs. actual resolution rate. A
        well-calibrated model has predicted ≈ actual in every bucket.
      </p>
      {error ? <p>API unreachable: {error}</p> : null}
      {report ? (
        <>
          <p>
            Brier: {report.brier_score?.toFixed(4) ?? "n/a"} · Log-loss:{" "}
            {report.log_loss?.toFixed(4) ?? "n/a"}
          </p>
          <table>
            <thead>
              <tr>
                <th>Bucket</th>
                <th style={{ textAlign: "right" }}>Predicted</th>
                <th style={{ textAlign: "right" }}>Actual</th>
                <th style={{ textAlign: "right" }}>N</th>
              </tr>
            </thead>
            <tbody>
              {report.buckets.map((b, i) => (
                <tr key={i}>
                  <td>
                    {(b.bucket_low * 100).toFixed(0)}–{(b.bucket_high * 100).toFixed(0)}%
                  </td>
                  <td style={{ textAlign: "right" }}>{(b.predicted_mean * 100).toFixed(1)}%</td>
                  <td style={{ textAlign: "right" }}>{(b.actual_rate * 100).toFixed(1)}%</td>
                  <td style={{ textAlign: "right", color: "var(--muted)" }}>{b.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      <h3 style={{ marginTop: 32 }}>Closing-Line Tracking</h3>
      <p style={{ color: "var(--muted)" }}>
        For resolved markets with ≥2 signals: did the market price move toward our edge between
        the first and last signal? A real edge persists into closing.
      </p>
      {closing && closing.resolved_markets_with_signals > 0 ? (
        <>
          <table>
            <tbody>
              <tr>
                <th>Resolved markets tracked</th>
                <td>{closing.resolved_markets_with_signals}</td>
              </tr>
              <tr>
                <th>Direction hit rate</th>
                <td>{closing.direction_hit_rate != null ? (closing.direction_hit_rate * 100).toFixed(1) + "%" : "—"}</td>
              </tr>
              <tr>
                <th>Avg market move toward our edge</th>
                <td>
                  {closing.avg_market_move_toward_edge != null
                    ? (closing.avg_market_move_toward_edge * 100).toFixed(2) + "pp"
                    : "—"}
                </td>
              </tr>
              <tr>
                <th>Outcome accuracy (model right side)</th>
                <td>
                  {closing.resolution_accuracy != null
                    ? (closing.resolution_accuracy * 100).toFixed(1) + "%"
                    : "—"}
                </td>
              </tr>
            </tbody>
          </table>

          {closing.samples.length > 0 ? (
            <>
              <h4 style={{ marginTop: 24 }}>Sample resolved markets</h4>
              <table>
                <thead>
                  <tr>
                    <th>Market</th>
                    <th style={{ textAlign: "right" }}>Initial Model</th>
                    <th style={{ textAlign: "right" }}>Initial Mkt</th>
                    <th style={{ textAlign: "right" }}>Final Mkt</th>
                    <th style={{ textAlign: "right" }}>Edge</th>
                    <th style={{ textAlign: "right" }}>Move →edge</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {closing.samples.map((s) => (
                    <tr key={s.market_id}>
                      <td>{s.question_text}</td>
                      <td style={{ textAlign: "right" }}>
                        {(s.initial_model_p * 100).toFixed(1)}%
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {(s.initial_market_p * 100).toFixed(1)}%
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {(s.final_market_p * 100).toFixed(1)}%
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          color: s.initial_edge > 0 ? "var(--accent)" : "var(--bad)",
                        }}
                      >
                        {s.initial_edge >= 0 ? "+" : ""}
                        {(s.initial_edge * 100).toFixed(1)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          color: s.market_moved_toward_edge > 0 ? "var(--accent)" : "var(--bad)",
                        }}
                      >
                        {s.market_moved_toward_edge >= 0 ? "+" : ""}
                        {(s.market_moved_toward_edge * 100).toFixed(1)}
                      </td>
                      <td>{s.outcome ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </>
      ) : (
        <p style={{ color: "var(--muted)" }}>
          No resolved markets with ≥2 signals yet. Once markets ingested today close, this
          section will populate.
        </p>
      )}
    </section>
  );
}
