# Alpha Edge

Prediction market intelligence engine. Generates probability-calibrated forecasts and model-vs-market edge scores for events on Kalshi and Polymarket.

See [docs/PRD.md](docs/PRD.md) for the full product spec.

## Layout

```
alpha-edge/
├── backend/              FastAPI service, ingestion, model, sentiment
│   ├── alpha_edge/
│   │   ├── api/          REST endpoints (section 9 of PRD)
│   │   ├── db/           SQLAlchemy models, session
│   │   ├── ingestion/    NBA stats, Basketball Reference, Kalshi, Polymarket
│   │   ├── sentiment/    Twitter, Reddit, news, NLP, credibility
│   │   ├── model/        Bayesian, Monte Carlo, calibration, Kelly, features
│   │   ├── market/       Edge scoring, signal tiers
│   │   └── workers/      Scheduled jobs (Prefect/Airflow target)
│   ├── alembic/          Migrations
│   └── tests/
├── frontend/             Next.js dashboard
├── docs/                 PRD and design notes
└── scripts/              Local dev helpers
```

## Quickstart

```bash
cp .env.example .env
docker compose up -d postgres redis
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn alpha_edge.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Development phases

Phase 1 — Data infrastructure (weeks 1–3)
Phase 2 — Statistical model (weeks 4–6)
Phase 3 — Sentiment layer (weeks 7–9)
Phase 4 — Market integration & API (weeks 10–11)
Phase 5 — Dashboard & calibration tracking (week 12)

See PRD section 10 for milestone detail.

## Status

v0 scaffold. Endpoints return stubs; ingestion and model code is unimplemented.
