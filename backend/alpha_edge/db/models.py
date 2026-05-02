"""SQLAlchemy models — schema mirrors PRD section 8."""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alpha_edge.db.session import Base


class Platform(str, enum.Enum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"


class Category(str, enum.Enum):
    SPORTS = "sports"
    POLITICS = "politics"
    FINANCE = "finance"


class Outcome(str, enum.Enum):
    YES = "YES"
    NO = "NO"


class SignalTier(str, enum.Enum):
    STRONG = "STRONG"
    LEAN = "LEAN"
    NONE = "NONE"
    FADE = "FADE"


class SentimentSource(str, enum.Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"


class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class HomeAway(str, enum.Enum):
    HOME = "home"
    AWAY = "away"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform, name="platform"))
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True, index=True)
    question_text: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(SAEnum(Category, name="category"))
    resolution_criteria: Mapped[str] = mapped_column(Text)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[Outcome | None] = mapped_column(
        SAEnum(Outcome, name="outcome"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    signals: Mapped[list[Signal]] = relationship(back_populates="market", cascade="all, delete-orphan")
    sentiment_events: Mapped[list[SentimentEvent]] = relationship(
        back_populates="market", cascade="all, delete-orphan"
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE")
    )
    model_probability: Mapped[float] = mapped_column(Float)
    confidence_interval_low: Mapped[float] = mapped_column(Float)
    confidence_interval_high: Mapped[float] = mapped_column(Float)
    market_price: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    signal_tier: Mapped[SignalTier] = mapped_column(SAEnum(SignalTier, name="signal_tier"))
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_weight: Mapped[float] = mapped_column(Float, default=0.0)
    stats_weight: Mapped[float] = mapped_column(Float, default=1.0)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    market: Mapped[Market] = relationship(back_populates="signals")


class SentimentEvent(Base):
    __tablename__ = "sentiment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE")
    )
    source: Mapped[SentimentSource] = mapped_column(SAEnum(SentimentSource, name="sentiment_source"))
    source_url: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[SentimentLabel] = mapped_column(SAEnum(SentimentLabel, name="sentiment_label"))
    credibility_weight: Mapped[float] = mapped_column(Float, default=0.5)
    novelty_score: Mapped[float] = mapped_column(Float, default=1.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    llm_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    market: Mapped[Market] = relationship(back_populates="sentiment_events")


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    opponent: Mapped[str] = mapped_column(Text)
    home_away: Mapped[HomeAway] = mapped_column(SAEnum(HomeAway, name="home_away"))
    minutes: Mapped[float] = mapped_column(Float, default=0.0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    rebounds: Mapped[int] = mapped_column(Integer, default=0)
    fg_pct: Mapped[float] = mapped_column(Float, default=0.0)
    ts_pct: Mapped[float] = mapped_column(Float, default=0.0)
    usage_rate: Mapped[float] = mapped_column(Float, default=0.0)
    raptor: Mapped[float] = mapped_column(Float, default=0.0)
    rest_days: Mapped[int] = mapped_column(Integer, default=0)
    injury_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
