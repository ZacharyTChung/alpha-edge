"""Seed demo markets + signals so the UI has something to render."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from alpha_edge.db.models import (
    Category,
    Market,
    Outcome,
    Platform,
    Signal,
    SignalTier,
)
from alpha_edge.db.session import SessionLocal
from alpha_edge.market.edge import classify_tier

DEMO = [
    ("kalshi", "sports", "Lakers win game 3 vs Nuggets?", 0.58, 0.49),
    ("polymarket", "sports", "LeBron James scores 25+ points tonight?", 0.71, 0.55),
    ("kalshi", "politics", "Will the Fed cut rates in June?", 0.42, 0.38),
    ("polymarket", "finance", "BTC closes above $100k on June 1?", 0.30, 0.41),
    ("kalshi", "sports", "Celtics advance to ECF?", 0.66, 0.62),
    ("polymarket", "sports", "Jokic over 28.5 points vs Lakers?", 0.55, 0.66),
    ("kalshi", "politics", "Senate passes spending bill before recess?", 0.48, 0.50),
    ("polymarket", "finance", "S&P 500 ends week green?", 0.62, 0.55),
]


def seed() -> None:
    rng = random.Random(7)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        for platform, category, question, model_p, market_price in DEMO:
            edge = model_p - market_price
            market = Market(
                id=uuid4(),
                platform=Platform(platform),
                question_text=question,
                category=Category(category),
                resolution_criteria=f"Resolves YES per official source. ({question})",
                close_time=now + timedelta(days=rng.randint(1, 14)),
                resolved_at=None,
                outcome=None,
            )
            db.add(market)
            db.flush()
            for i in range(4):
                jitter = rng.uniform(-0.03, 0.03)
                p = max(0.02, min(0.98, model_p + jitter))
                e = p - market_price
                db.add(
                    Signal(
                        id=uuid4(),
                        market_id=market.id,
                        model_probability=p,
                        confidence_interval_low=max(0.0, p - 0.06),
                        confidence_interval_high=min(1.0, p + 0.06),
                        market_price=market_price,
                        edge=e,
                        signal_tier=classify_tier(e),
                        sentiment_score=rng.uniform(-0.4, 0.4),
                        sentiment_weight=0.3,
                        stats_weight=0.7,
                        generated_at=now - timedelta(hours=24 - i * 6),
                    )
                )

        # one resolved market so calibration has at least one row
        resolved = Market(
            id=uuid4(),
            platform=Platform.KALSHI,
            question_text="Warriors made the play-in (resolved)?",
            category=Category.SPORTS,
            resolution_criteria="Resolved YES.",
            close_time=now - timedelta(days=2),
            resolved_at=now - timedelta(days=1),
            outcome=Outcome.YES,
        )
        db.add(resolved)
        db.flush()
        db.add(
            Signal(
                id=uuid4(),
                market_id=resolved.id,
                model_probability=0.72,
                confidence_interval_low=0.66,
                confidence_interval_high=0.78,
                market_price=0.65,
                edge=0.07,
                signal_tier=classify_tier(0.07),
                sentiment_score=0.2,
                sentiment_weight=0.3,
                stats_weight=0.7,
                generated_at=now - timedelta(days=2),
            )
        )
        db.commit()
        print(f"seeded {len(DEMO) + 1} markets")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
