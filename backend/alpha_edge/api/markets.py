from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Market
from alpha_edge.schemas import MarketOut

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("", response_model=list[MarketOut])
def list_markets(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_session),
) -> list[Market]:
    stmt = select(Market).order_by(Market.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{market_id}", response_model=MarketOut)
def get_market(market_id: UUID, db: Session = Depends(get_session)) -> Market:
    market = db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return market
