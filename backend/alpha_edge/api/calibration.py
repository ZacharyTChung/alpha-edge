from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from alpha_edge.db import get_session
from alpha_edge.model.calibration import build_calibration_report
from alpha_edge.schemas import CalibrationReport

router = APIRouter(tags=["calibration"])


@router.get("/calibration", response_model=CalibrationReport)
def get_calibration(
    bucket_count: int = 10,
    db: Session = Depends(get_session),
) -> CalibrationReport:
    return build_calibration_report(db, bucket_count=bucket_count)
