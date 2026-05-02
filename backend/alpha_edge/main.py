from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alpha_edge.api import admin, alerts, calibration, edge, markets, players, sentiment, signals, stats
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(markets.router)
    app.include_router(signals.router)
    app.include_router(sentiment.router)
    app.include_router(players.router)
    app.include_router(calibration.router)
    app.include_router(edge.router)
    app.include_router(alerts.router)
    app.include_router(admin.router)
    app.include_router(stats.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
