"""Calibration: Platt scaling, isotonic regression, reliability diagram aggregation.

PRD section 6.1 / 12.1 — every reported probability should match empirical frequencies.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db.models import Market, Outcome, Signal
from alpha_edge.schemas import CalibrationBucket, CalibrationReport


def build_calibration_report(db: Session, bucket_count: int = 10) -> CalibrationReport:
    """Aggregate resolved markets into probability buckets and compute metrics.

    Returns empty buckets when there is no resolved data yet (early in the
    project's life). Brier score and log-loss are computed only over resolved
    markets.
    """
    stmt = (
        select(Signal, Market.outcome)
        .join(Market, Signal.market_id == Market.id)
        .where(Market.outcome.is_not(None))
    )
    rows = db.execute(stmt).all()

    if not rows:
        return CalibrationReport(brier_score=None, log_loss=None, buckets=[])

    width = 1.0 / bucket_count
    sums: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(bucket_count)]
    brier_total = 0.0
    log_loss_total = 0.0
    eps = 1e-9

    for signal, outcome in rows:
        p = float(signal.model_probability)
        y = 1.0 if outcome == Outcome.YES else 0.0
        idx = min(int(p / width), bucket_count - 1)
        sums[idx][0] += p
        sums[idx][1] += y
        sums[idx][2] += 1.0
        brier_total += (p - y) ** 2
        p_clamped = min(max(p, eps), 1.0 - eps)
        log_loss_total -= y * (p_clamped) + (1.0 - y) * (1.0 - p_clamped)

    n = len(rows)
    buckets = [
        CalibrationBucket(
            bucket_low=i * width,
            bucket_high=(i + 1) * width,
            predicted_mean=(s[0] / s[2]) if s[2] else 0.0,
            actual_rate=(s[1] / s[2]) if s[2] else 0.0,
            count=int(s[2]),
        )
        for i, s in enumerate(sums)
    ]
    return CalibrationReport(
        brier_score=brier_total / n,
        log_loss=log_loss_total / n,
        buckets=buckets,
    )
