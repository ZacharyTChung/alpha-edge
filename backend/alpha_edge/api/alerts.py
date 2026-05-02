from uuid import uuid4

from fastapi import APIRouter

from alpha_edge.schemas import AlertSubscriptionIn, AlertSubscriptionOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/subscribe", response_model=AlertSubscriptionOut)
def subscribe(payload: AlertSubscriptionIn) -> AlertSubscriptionOut:
    return AlertSubscriptionOut(
        id=uuid4(),
        webhook_url=payload.webhook_url,
        min_edge=payload.min_edge,
        tiers=payload.tiers,
    )
