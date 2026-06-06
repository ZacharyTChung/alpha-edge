# Alpha Edge

**Prediction market intelligence engine.** Generates probability-calibrated forecasts and edge scores for binary markets on Kalshi and Polymarket by fusing live market prices with multi-source sentiment classified by Claude.

> Status: v0.2 working prototype — markets, sentiment, and signal generation are live end-to-end. Statistical priors (XGBoost / regression on player-level data) are deferred to Phase 2. The current model uses the market price as the prior and updates it with a relevance-weighted sentiment likelihood.

---

## What it does

Every refresh, the system:

1. **Polls live markets** from Polymarket Gamma API and Kalshi public read API. Upserts ~100 markets with current YES prices and liquidity.
2. **Pulls fresh evidence** for each market from 8+ source types — Google News (per-market query), Bluesky public search, Reddit (RSS), RotoWire / ESPN / Yahoo / CBS RSS, ESPN news API, X via syndication, Hacker News for finance/politics.
3. **Classifies each text snippet** with Claude Sonnet 4.6 against the specific market question, scoring `sentiment`, `relevance`, `impact_direction`, and `confidence`. Drops anything Claude judges off-topic; weights remaining evidence by source credibility × confidence. If no `ANTHROPIC_API_KEY` is configured, this step transparently falls back to VADER (rule-based) sentiment — the system runs fully keyless, trading context-awareness for zero cost.
4. **Computes a Bayesian posterior** by combining the market-implied prior with the weighted sentiment likelihood:

   ```
   posterior_log_odds = log_odds(market_price) + 0.6 · Σ(score · cred · novelty) / Σ(cred · novelty)
   edge = posterior - market_price
   tier = STRONG ≥ +10pp · LEAN ≥ +4pp · FADE ≤ −10pp
   ```

5. **Tracks closing-line movement** on resolved markets — does the market price move toward the model's edge between the first and last signal? That's the only honest backtest of whether the system has alpha.

A Next.js dashboard renders the markets list, an edge report with filter pills, per-market sentiment evidence (with Claude's one-sentence reasoning), price-history sparklines, calibration tables, and the closing-line tracking section.

---

## Live stats (snapshot from this session)

| Metric | Value |
|---|---|
| Markets tracked | 105 (104 open, 1 resolved) |
| Categories | sports 74, politics 25, finance 6 |
| Liquidity range | $5 – $1.23M (avg $72k) |
| Signals generated | 264 |
| Sentiment events captured | 1,076 |
| Source breakdown | NEWS 736, REDDIT 222, TWITTER 118 |
| LLM-classified events (after relevance filter) | 20 (this session, ramping as more refreshes run) |
| Latest tier counts | 4 STRONG · 10 LEAN · 90 NONE · 1 FADE |

A typical priority refresh ingests ~9 liquid sports markets, generates ~50 candidate texts, surfaces ~20 after the LLM relevance filter, and writes 9 signals — all in ~60s with the prompt cache warm.

---

## Architecture

```
                ┌──────────────────────────────────────────┐
                │  Next.js dashboard (localhost:3000)      │
                │  / · /edge · /calibration · /markets/<id>│
                └──────────────────┬───────────────────────┘
                                   │ fetch
┌──────────────────────────────────▼─────────────────────────────────────┐
│  FastAPI (localhost:8000)                                              │
│  /markets · /edge-report · /calibration · /admin/refresh[-priority]    │
│  /admin/closing-line-tracking · /stats · Swagger at /docs              │
└────────┬─────────────────────────┬─────────────────────────┬───────────┘
         │                         │                         │
         ▼                         ▼                         ▼
   Postgres 16                  Pipeline                  Anthropic API
   (port 5433)              workers/tasks.py             Sonnet 4.6
   markets, signals,                                  (prompt-cached system
   sentiment_events                                       prompt)
```

The pipeline is one chain of pure functions: `poll_polymarket → poll_kalshi → scrape_sentiment → classify (LLM or VADER fallback) → predict_market → write_signal`. All state lives in Postgres; nothing is in-memory between refreshes.

---

## Data sources

| Source | Auth needed | What it provides | Where wired |
|---|---|---|---|
| Polymarket Gamma API | none | Active markets + YES/NO prices + USD volume | `ingestion/polymarket.py` |
| Kalshi public read API | none | NBA/NFL/MLB/NHL game markets + last-traded prices + open interest | `ingestion/kalshi.py` |
| Google News RSS | none | Per-market query-targeted articles, recency filtered | `sentiment/news.py` |
| Bluesky public search | none | Real-time public posts (sports media is increasingly here) | `sentiment/bluesky.py` |
| Reddit RSS | none | r/nba, r/sportsbook, r/nfl, r/soccer, r/kalshimarkets | `sentiment/reddit.py` |
| RotoWire RSS | none | Sports-specialist injury wire (highest credibility weight: 0.9) | `sentiment/news.py` |
| ESPN news API | none | Structured JSON headlines for NBA/NFL/MLB | `sentiment/news.py` |
| ESPN / Yahoo / CBS RSS | none | Broad sports news fallback | `sentiment/news.py` |
| X syndication endpoint | none | Hand-picked beat reporters (Shams, Windhorst, etc.) — popular tweets only | `sentiment/x_syndication.py` |
| Hacker News (Algolia) | none | Finance / political market context | `sentiment/hn.py` |
| Basketball Reference | none | Recent player gamelogs (top 80 NBA players, hardcoded slug map) | `ingestion/basketball_ref.py` |
| Anthropic Messages API | API key | Per-market batched sentiment classification | `sentiment/llm.py` |
| Reddit official API (PRAW) | optional client_id/secret | Comment threads + deep search if you have it | `sentiment/reddit.py` |
| Twitter v2 search | optional bearer token | Real-time tweet search ($200/mo Basic) | `sentiment/twitter.py` |

Everything except the last three works with no signup. Anthropic key is the only ongoing cost.

---

## The model

`backend/alpha_edge/model/predict.py`

```python
posterior_log_odds = log_odds(prior) + K_SENTIMENT * weighted_aggregate
edge = posterior - market_price
```

Where:
- `prior = market_price` (Phase 1 — the market is the consensus)
- `K_SENTIMENT = 0.6` — fully-positive corpus shifts log-odds by +0.6 (≈ +0.15 prob at p=0.5)
- `weighted_aggregate = Σ(score_i · credibility_i · novelty_i) / Σ(credibility_i · novelty_i)`

Credibility is set per-source in `sentiment/credibility.py`, then scaled by Claude's confidence on each text:

```python
final_credibility = base_credibility * (0.5 + 0.5 * llm_confidence)
```

Confidence intervals come from a heuristic: width ∝ stdev of evidence scores / √N, with a floor that widens when there's little evidence. **This is not a real posterior** — replacing it with proper Monte Carlo over component distributions is the next major modeling task.

Tier thresholds (`market/edge.py`):

| Tier | Edge |
|---|---|
| STRONG | ≥ +10pp |
| LEAN | ≥ +4pp |
| FADE | ≤ −10pp |
| NONE | otherwise |

---

## What's deferred (the honest list)

1. **Real statistical prior.** Right now `model_p` starts from `market_price`. The PRD calls for fitting logistic regression / XGBoost on player-level box-score features. Until that lands, the "model" is essentially a sentiment-shifted market consensus. The Bayesian framework is in place; the prior generator is not.
2. **Player → market resolution.** BBRef gamelog ingestion exists with an 80-name slug map, but matching a player to an arbitrary market question requires NER. Currently we feed BBRef stats into the LLM context as a string, not into a regression.
3. **Calibration is uniform.** All probabilities use the same `K_SENTIMENT` constant. Real systems learn per-category and per-source-mix calibration coefficients.
4. **CI is heuristic.** Should be Monte Carlo over component distributions per the PRD.
5. **Closing-line backtest needs soak time.** The tracking endpoint works; the metric is empty until ingested markets resolve over the next days/weeks.

---

## Quickstart

Requires Docker, Python 3.11+, and Node 20+. An Anthropic API key is **optional**: without it, sentiment classification automatically falls back to VADER (rule-based, no cost) and the app runs fully keyless — set a key only to upgrade to LLM-grade, context-aware sentiment.

```bash
# 1. Postgres (port 5433 to avoid conflict with system instances)
docker run -d --name alpha-edge-pg \
  -e POSTGRES_USER=alpha -e POSTGRES_PASSWORD=alpha -e POSTGRES_DB=alpha_edge \
  -p 5433:5432 postgres:16

# 2. Backend
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install feedparser vaderSentiment praw tweepy beautifulsoup4 anthropic

cp ../.env.example .env
# edit backend/.env to set DATABASE_URL=postgresql+psycopg://alpha:alpha@localhost:5433/alpha_edge
# optional: ANTHROPIC_API_KEY=sk-ant-... for LLM-grade sentiment

alembic upgrade head
uvicorn alpha_edge.main:app --host 127.0.0.1 --port 8000

# 3. Frontend (in another terminal)
cd frontend
npm install
npm run dev    # http://localhost:3000

# 4. Trigger the first refresh
curl -X POST http://localhost:8000/admin/refresh
```

Then open http://localhost:3000 and click **Priority** to refresh sports markets quickly, or **Full refresh** for everything.

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/stats` | Dashboard counts |
| GET | `/markets?limit=N` | List markets |
| GET | `/markets/{id}` | Single market |
| GET | `/markets/{id}/signals` | Signal history |
| GET | `/markets/{id}/sentiment` | Sentiment evidence (with LLM reasoning) |
| GET | `/edge-report?min_edge=0.03` | Open markets above edge threshold |
| GET | `/calibration` | Reliability table + Brier / log-loss |
| GET | `/admin/closing-line-tracking` | Edge persistence on resolved markets |
| POST | `/admin/refresh` | Full pipeline (~2 min) |
| POST | `/admin/refresh-priority` | Sports + ≥$1k liquidity (~60s) |
| GET | `/docs` | Swagger UI |

---

## Project structure

```
alpha-edge/
├── backend/
│   ├── alpha_edge/
│   │   ├── api/              FastAPI routers (markets, signals, sentiment, edge, calibration, admin, stats, alerts, players)
│   │   ├── db/               SQLAlchemy models + session
│   │   ├── ingestion/        polymarket, kalshi, basketball_ref, nba_stats
│   │   ├── sentiment/        news (RSS + Google News + ESPN), bluesky, reddit, x_syndication, twitter, hn, nlp (VADER), llm (Claude), credibility
│   │   ├── model/            bayesian, kelly, calibration, predict, monte_carlo, train, features
│   │   ├── market/           edge tier classification + edge report
│   │   ├── workers/          tasks.py — refresh_all, refresh_priority, scrape_sentiment, regenerate_signals
│   │   ├── config.py         Pydantic settings (env-driven)
│   │   ├── schemas.py        Pydantic API I/O contracts
│   │   └── main.py           FastAPI app factory
│   ├── alembic/              3 migrations: init_schema, add_market_external_id, add_liquidity_reasoning_relevance
│   └── tests/                pytest: bayesian, kelly, edge_tier, health
├── frontend/
│   ├── app/
│   │   ├── page.tsx          markets list + stats banner + refresh
│   │   ├── edge/             edge report with filter pills
│   │   ├── calibration/      reliability + closing-line tracking
│   │   └── markets/[id]/     market detail with sparkline + LLM-reasoned sentiment
│   └── lib/api.ts            typed fetch client
├── scripts/
│   └── seed_demo.py          (legacy demo data; live ingestion replaces this)
├── docs/
│   └── PRD.md                Original product spec
├── docker-compose.yml        Postgres + Redis + backend + frontend
├── .env.example
└── README.md
```

44 Python files, 10 TypeScript files, 3 alembic migrations.

---

## Costs

With the LLM enabled and prompt cache warm:

| Action | Cost |
|---|---|
| Priority refresh (~10 markets) | ~$0.05 |
| Full refresh (~100 markets) | ~$0.50 |
| Cache write (first call) | 1.25× input price for ~2.1k tokens |
| Cache read (subsequent calls within 5 min) | 0.1× input price |

The system gates LLM classification on `liquidity ≥ $1k` to avoid spending API calls on novelty markets. To cut costs further, switch to Haiku 4.5 via `ANTHROPIC_SENTIMENT_MODEL=claude-haiku-4-5` in `.env` — accepts ~80% of the quality at 30% of the cost.

---

## What I'd build next

1. **Phase 2 statistical prior.** Wire NBA Stats / BBRef gamelog into a regression for player-prop markets so the prior isn't just `market_price`.
2. **Auto-refresh scheduler.** Cron every 15–30 min during NBA hours.
3. **Bet-tracking page.** Log "I bet $X at price Y" so we can compare your bets to the model's recommendations and the closing line.
4. **Real Monte Carlo confidence intervals.** Replace the heuristic CI with bootstrap over component distributions.
5. **Per-source calibration.** Learn which sources actually predict outcomes and update credibility weights from data, not hardcoded constants.

---

## License

Personal project. No license attached — ask before reusing.
