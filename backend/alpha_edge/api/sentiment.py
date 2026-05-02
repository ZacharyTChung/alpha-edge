from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import SentimentEvent
from alpha_edge.schemas import SentimentEventOut

router = APIRouter(tags=["sentiment"])


@router.get("/markets/{market_id}/sentiment", response_model=list[SentimentEventOut])
def list_market_sentiment(
    market_id: UUID,
    limit: int = 200,
    db: Session = Depends(get_session),
) -> list[SentimentEvent]:
    stmt = (
        select(SentimentEvent)
        .where(SentimentEvent.market_id == market_id)
        .order_by(
            SentimentEvent.detected_at.desc(),
            SentimentEvent.credibility_weight.desc(),
        )
        .limit(limit)
    )
    return list(db.scalars(stmt))
