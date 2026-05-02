from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.db.models import PlayerGameStats
from alpha_edge.schemas import PlayerGameStatsOut

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/{player_id}/stats", response_model=list[PlayerGameStatsOut])
def get_player_stats(
    player_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 500,
    db: Session = Depends(get_session),
) -> list[PlayerGameStats]:
    stmt = select(PlayerGameStats).where(PlayerGameStats.player_id == player_id)
    if start_date is not None:
        stmt = stmt.where(PlayerGameStats.game_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(PlayerGameStats.game_date <= end_date)
    stmt = stmt.order_by(PlayerGameStats.game_date.desc()).limit(limit)
    return list(db.scalars(stmt))
