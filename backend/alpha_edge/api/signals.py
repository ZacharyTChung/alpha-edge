from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import Signal
from alpha_edge.schemas import SignalOut

router = APIRouter(tags=["signals"])


@router.get("/markets/{market_id}/signals", response_model=list[SignalOut])
def list_market_signals(
    market_id: UUID,
    limit: int = 200,
    db: Session = Depends(get_session),
) -> list[Signal]:
    stmt = (
        select(Signal)
        .where(Signal.market_id == market_id)
        .order_by(Signal.generated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
