from contextlib import asynccontextmanager

from fastapi import FastAPI

from alpha_edge.api import alerts, calibration, edge, markets, players, sentiment, signals
from alpha_edge.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Alpha Edge",
        version="0.1.0",
        description="Prediction market intelligence engine",
        lifespan=lifespan,
    )

    app.include_router(markets.router)
    app.include_router(signals.router)
    app.include_router(sentiment.router)
    app.include_router(players.router)
    app.include_router(calibration.router)
    app.include_router(edge.router)
    app.include_router(alerts.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
