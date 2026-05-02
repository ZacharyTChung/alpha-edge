from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.market.edge import current_edge_report
from alpha_edge.schemas import EdgeReportItem

router = APIRouter(tags=["edge"])


@router.get("/edge-report", response_model=list[EdgeReportItem])
def get_edge_report(
    min_edge: float = 0.05,
    limit: int = 50,
    db: Session = Depends(get_session),
) -> list[EdgeReportItem]:
    return current_edge_report(db, min_edge=min_edge, limit=limit)
