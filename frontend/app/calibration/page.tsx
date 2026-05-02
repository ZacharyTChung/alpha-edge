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

  return (
    <section>
      <h2>Calibration</h2>
      <p style={{ color: "var(--muted)" }}>
        Reliability diagram: predicted probability bucket vs. actual resolution rate.
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
                <th>Predicted</th>
                <th>Actual</th>
                <th>N</th>
              </tr>
            </thead>
            <tbody>
              {report.buckets.map((b, i) => (
                <tr key={i}>
                  <td>
                    {(b.bucket_low * 100).toFixed(0)}–{(b.bucket_high * 100).toFixed(0)}%
                  </td>
                  <td>{(b.predicted_mean * 100).toFixed(1)}%</td>
                  <td>{(b.actual_rate * 100).toFixed(1)}%</td>
                  <td>{b.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
