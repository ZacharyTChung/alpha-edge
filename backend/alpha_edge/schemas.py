"""Pydantic response/request schemas for the API."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from alpha_edge.db.models import (
    Category,
    HomeAway,
    Outcome,
    Platform,
    SentimentLabel,
    SentimentSource,
    SignalTier,
)


class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: Platform
    question_text: str
    category: Category
    resolution_criteria: str
    close_time: datetime
    resolved_at: datetime | None
    outcome: Outcome | None


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    market_id: UUID
    model_probability: float = Field(ge=0, le=1)
    confidence_interval_low: float = Field(ge=0, le=1)
    confidence_interval_high: float = Field(ge=0, le=1)
    market_price: float = Field(ge=0, le=1)
    edge: float
    signal_tier: SignalTier
    sentiment_score: float
    sentiment_weight: float
    stats_weight: float
    generated_at: datetime


class SentimentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    market_id: UUID
    source: SentimentSource
    source_url: str
    entity: str
    raw_text: str
    sentiment: SentimentLabel
    credibility_weight: float
    novelty_score: float
    detected_at: datetime


class PlayerGameStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    player_id: UUID
    game_date: date
    opponent: str
    home_away: HomeAway
    minutes: float
    points: int
    assists: int
    rebounds: int
    fg_pct: float
    ts_pct: float
    usage_rate: float
    raptor: float
    rest_days: int
    injury_flag: bool


class CalibrationBucket(BaseModel):
    bucket_low: float
    bucket_high: float
    predicted_mean: float
    actual_rate: float
    count: int


class CalibrationReport(BaseModel):
    brier_score: float | None
    log_loss: float | None
    buckets: list[CalibrationBucket]


class EdgeReportItem(BaseModel):
    market_id: UUID
    question_text: str
    model_probability: float
    market_price: float
    edge: float
    signal_tier: SignalTier


class AlertSubscriptionIn(BaseModel):
    webhook_url: str
    min_edge: float = Field(default=0.10, ge=0, le=1)
    tiers: list[SignalTier] = Field(default_factory=lambda: [SignalTier.STRONG])


class AlertSubscriptionOut(BaseModel):
    id: UUID
    webhook_url: str
    min_edge: float
    tiers: list[SignalTier]
