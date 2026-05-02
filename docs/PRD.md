# ALPHA EDGE — Prediction Market Intelligence Engine
## Product Requirements Document v1.0

**Status:** Draft — For Internal Development
**Version:** 1.0
**Target Markets:** Kalshi, Polymarket, Manifold
**Primary Consumers:** Quant firms, prop traders, algo funds
**Document Owner:** Founder / Lead Engineer

---

## 1. Executive Summary

Alpha Edge is a quantitative prediction market intelligence engine that generates probability-calibrated forecasts for events listed on Kalshi and Polymarket. The system fuses three signal layers — historical statistical data, real-time sentiment derived from social and news sources, and probabilistic modeling adapted from institutional quantitative finance — to produce market edges that can be acted on programmatically or surfaced to analysts.

The core thesis is that prediction markets are systematically mispriced because retail participants underweight base rates and overweight recency/sentiment. Alpha Edge exploits this by building a rigorous statistical prior, then updating it with a sentiment layer that captures information not yet reflected in market prices.

> **Core Value Proposition:** Where existing prediction market tools give users a news feed or a simple price chart, Alpha Edge gives them a calibrated probability with a confidence interval, a decomposed signal breakdown, and a model-vs-market edge score — the same output structure used by institutional quant desks.

---

## 2. Problem Statement

### 2.1 Market Inefficiency Hypothesis

Prediction markets like Kalshi and Polymarket are growing in liquidity and legitimacy, but price discovery remains inefficient for a structural reason: most participants are not quantitatively sophisticated. They anchor on headlines, recent events, and narrative — not base rates, regression to the mean, or Bayesian updating.

This creates a repeatable edge for a system that does the following:
- Builds a strong statistical prior from historical performance data
- Detects sentiment shifts that move markets before prices adjust
- Sizes confidence intervals honestly rather than over-fitting to recent data
- Tracks its own calibration — when it says 70%, it should be right ~70% of the time

### 2.2 Existing Tool Gaps

| Existing Tool | Gap |
|---|---|
| Data aggregators | Provide raw stats and news feeds. No probability outputs, no model-vs-market comparison. |
| Simple ML models | Predict outcomes but ignore market prices — miss the point that edge = model vs market, not just correct prediction. |
| Social listening tools | Surface sentiment but don't weight it against historical base rates. |
| Quant firm tooling | Exists internally at well-capitalized firms. Not accessible to smaller desks or independent traders. |

---

## 3. Goals & Non-Goals

### 3.1 Goals

- **Primary:** Build a calibrated probability model for sports events on Kalshi and Polymarket
- **Primary:** Integrate historical statistical data, real-time social/news sentiment, and quant modeling techniques into a unified scoring framework
- **Primary:** Produce a model-vs-market edge score for every covered market
- **Primary:** Ship a usable internal API that can power a dashboard or be queried by a trading bot
- **Secondary:** Expand to political events and financial markets as a v2 module
- **Secondary:** Open-source a calibration evaluation library modeled after AfterQuery's benchmark methodology

### 3.2 Non-Goals

- This is not a fully automated trading bot in v1 — it produces signals, not executed trades
- Not designed to handle high-frequency markets where latency is sub-second critical
- Not a general-purpose sports prediction site for retail users
- Not a replacement for a full quantitative research platform like QuantConnect or Numerai

---

## 4. Target Users

| User Type | Description | Priority |
|---|---|---|
| Quant traders | Individual or small-firm traders who systematically trade prediction markets and want model-backed signals | Primary |
| Prop trading desks | Small to mid-size prop shops looking for systematic edges in event markets | Primary |
| Algo/quant funds | Funds deploying capital in prediction markets programmatically via API | Primary |
| Research analysts | Individuals building proprietary models who want a data layer and benchmark | Secondary |
| Independent developers | Engineers building trading tools who want the scoring API as a data source | Secondary |

---

## 5. System Architecture Overview

Alpha Edge is built around four distinct layers that each handle a specific part of the signal generation pipeline. Each layer is independently deployable, testable, and replaceable.

### 5.1 Layer 1 — Historical Data Ingestion

This is the statistical backbone. For sports markets, this means ingesting structured player and team performance data over multiple seasons. For an NBA example using LeBron James:

- Per-game box score stats (PTS, AST, REB, MIN, FG%, TS%, usage rate)
- Advanced metrics: RAPTOR, EPM, BPM, on/off splits
- Contextual factors: home/away, rest days, back-to-backs, opponent defensive rating
- Injury status history and return-from-injury performance degradation curves
- Market-specific historical outcomes: did the market resolve YES/NO and what was the price at various time windows

**Data Sources (v1):**
NBA Stats API (official, free) · Basketball Reference (scraping) · Sports Reference · Stathead · Rotowire injury feed · Historical Kalshi and Polymarket resolution data via their APIs

### 5.2 Layer 2 — Sentiment & News Intelligence

This layer scrapes, parses, and scores real-time information that may not yet be priced into the market. This is where the alpha lives — detecting signal before the market updates.

#### Data Sources
- Twitter/X: keyword + entity monitoring (player name, team, injury, load management)
- Reddit: r/nba, r/sportsbook, r/KalshiMarkets — for crowd sentiment and early injury rumors
- Beat reporters and credentialed journalists: faster than official channels on injury news
- Rotowire / RotoGrinders: injury status updates with timestamps
- Google Trends: search volume spikes as a proxy for information dissemination

#### NLP Processing Pipeline
- Entity extraction: identify player, team, market references in raw text
- Sentiment classification: positive / negative / neutral per entity per document
- Claim extraction: structured parsing of injury reports ("LeBron listed as questionable with ankle")
- Novelty detection: weight new information vs. re-circulation of existing information
- Source credibility weighting: Adrian Wojnarowski tweet > anonymous Reddit post

> **Key Design Principle:** Sentiment is not additive to the model — it is used to update a Bayesian prior. The historical statistical model sets the base probability. Sentiment shifts that probability based on its credibility weight, recency, and relevance to the specific market question.

### 5.3 Layer 3 — Quantitative Probability Engine

This is where the statistical and probability techniques borrowed from institutional quant finance are applied. The goal is to produce a well-calibrated probability estimate, not just a directional prediction.

#### Core Statistical Techniques
- **Bayesian updating:** start with a prior from historical data, update with likelihood derived from sentiment and contextual signals
- **Logistic regression / gradient boosted classifiers:** trained on historical market questions and their resolution outcomes
- **Monte Carlo simulation:** for markets with continuous underlying variables (e.g., "LeBron scores 25+ points"), run 10,000+ simulations from his scoring distribution
- **Kelly Criterion:** given model probability P and market price Q, compute optimal bet size as edge / odds
- **Calibration curves:** Platt scaling and isotonic regression to ensure model probabilities match empirical frequencies
- **Feature importance / SHAP values:** decompose which signals are driving each specific market prediction

#### Uncertainty Quantification
- Every probability output comes with a confidence interval, not just a point estimate
- Model disagreement across sub-models is surfaced as an uncertainty flag
- Sentiment-vs-stats conflict is detected and flagged separately (e.g., stats say 80% but sentiment is very negative)

### 5.4 Layer 4 — Market Integration & Edge Scoring

This layer connects the model to live market prices and produces the final actionable output.

- Poll Kalshi and Polymarket APIs at configurable intervals for current market prices
- Compute model probability minus market price = raw edge
- Adjust edge for liquidity (thin markets get penalized), time to resolution, and model confidence
- Produce a signal tier: Strong Edge / Lean / No Edge / Fade (against the market)
- Log all predictions with timestamps so calibration can be tracked over time

---

## 6. Feature Requirements

### 6.1 Core Features — v1

| Feature | Description | Priority |
|---|---|---|
| Historical data pipeline | Automated ingestion and normalization of player/team stats from multiple sources into a structured database | P0 |
| Sentiment scraper | Real-time monitoring of Twitter, Reddit, and news sources for entity-level sentiment signals | P0 |
| Probability engine | Bayesian + ML model producing calibrated probability estimates with confidence intervals | P0 |
| Market connector | Live price polling from Kalshi and Polymarket APIs, edge computation, signal tier output | P0 |
| REST API | Internal API endpoints for querying signals, market coverage, and model outputs | P0 |
| Calibration tracker | Logging and visualization of model accuracy over time — predicted probability vs. actual resolution rate | P0 |
| Dashboard (basic) | Simple Next.js UI showing covered markets, current signals, edge scores, and confidence intervals | P1 |
| Alert system | Webhook or push notification when a high-confidence edge appears or when sentiment spike is detected | P1 |
| SHAP decomposition view | Per-market breakdown of which features are driving the probability estimate | P1 |
| Kelly sizing calculator | Given a model probability and market price, output optimal position size as % of bankroll | P2 |
| Backtesting module | Run the model on historical market data to evaluate calibration and returns | P2 |

### 6.2 v2 Features (Future)

- Political event markets (elections, policy outcomes)
- Financial event markets (Fed rate decisions, earnings surprises)
- Multi-market correlation detection (correlated events that markets misprice independently)
- Automated execution via Kalshi/Polymarket trading APIs
- Portfolio-level exposure management and risk limits

---

## 7. Technical Stack

| Layer | Technology |
|---|---|
| Backend | Python (FastAPI) — data pipelines, model training, API server |
| Frontend | Next.js (React) — internal dashboard and signal explorer |
| Database | PostgreSQL — structured market data, predictions, resolutions · Redis — real-time sentiment cache and job queue |
| Data pipeline | Apache Airflow or Prefect — scheduled ingestion jobs, model retraining triggers |
| ML / Stats | scikit-learn, XGBoost, PyMC (Bayesian modeling), SHAP, scipy.stats |
| NLP / Sentiment | spaCy (NER), HuggingFace transformers (sentiment), newspaper3k (article parsing) |
| Scraping | Playwright (JS-rendered pages), httpx + BeautifulSoup (static), Tweepy (Twitter API) |
| Market APIs | Kalshi REST API, Polymarket CLOB API (Gamma Markets) |
| Infrastructure | Docker + docker-compose (local) · AWS ECS or Fly.io (production) · S3 for data storage |
| Monitoring | Prometheus + Grafana for pipeline health · custom calibration dashboard |

---

## 8. Core Data Models

### 8.1 Market
```
markets
- id (uuid, primary key)
- platform (enum: kalshi | polymarket)
- question_text (text)
- category (enum: sports | politics | finance)
- resolution_criteria (text)
- close_time (timestamptz)
- resolved_at (timestamptz, nullable)
- outcome (enum: YES | NO | null)
- created_at (timestamptz)
```

### 8.2 Signal
```
signals
- id (uuid, primary key)
- market_id (uuid, foreign key → markets)
- model_probability (float, 0–1)
- confidence_interval_low (float, 0–1)
- confidence_interval_high (float, 0–1)
- market_price (float, 0–1)
- edge (float: model_probability - market_price)
- signal_tier (enum: STRONG | LEAN | NONE | FADE)
- sentiment_score (float)
- sentiment_weight (float)
- stats_weight (float)
- generated_at (timestamptz)
```

### 8.3 Sentiment Event
```
sentiment_events
- id (uuid, primary key)
- market_id (uuid, foreign key → markets)
- source (enum: twitter | reddit | news)
- source_url (text)
- entity (text)
- raw_text (text)
- sentiment (enum: positive | negative | neutral)
- credibility_weight (float)
- novelty_score (float)
- detected_at (timestamptz)
```

### 8.4 Player Stats (Sports)
```
player_game_stats
- id (uuid, primary key)
- player_id (uuid)
- game_date (date)
- opponent (text)
- home_away (enum: home | away)
- minutes (float)
- points (int)
- assists (int)
- rebounds (int)
- fg_pct (float)
- ts_pct (float)
- usage_rate (float)
- raptor (float)
- rest_days (int)
- injury_flag (boolean)
- created_at (timestamptz)
```

---

## 9. API Specification (v1)

| Endpoint | Description |
|---|---|
| GET /markets | List all tracked markets with current prices and signal tiers |
| GET /markets/:id | Full detail for a single market — probability, confidence interval, edge, feature breakdown |
| GET /markets/:id/signals | Historical signal log for a market with timestamps |
| GET /markets/:id/sentiment | Sentiment events associated with a market, sorted by recency and credibility |
| GET /players/:id/stats | Historical stats for a player with optional date range and context filters |
| GET /calibration | Aggregate calibration report — predicted probability buckets vs. actual resolution rates |
| GET /edge-report | Current high-edge markets sorted by signal strength |
| POST /alerts/subscribe | Register a webhook URL to receive alerts when a strong edge is detected |

---

## 10. Development Phases & Milestones

### Phase 1 — Data Infrastructure (Weeks 1–3)
- Set up PostgreSQL + Redis with Docker
- Build NBA stats ingestion pipeline (NBA API + Basketball Reference)
- Build Kalshi and Polymarket market polling jobs
- Schema design and initial data population for NBA markets
- Unit tests for all ingestion pipelines

### Phase 2 — Statistical Model (Weeks 4–6)
- Build historical feature engineering for player stats
- Train baseline logistic regression + XGBoost classifiers on historical NBA market outcomes
- Implement Monte Carlo simulator for points/rebounds/assists props
- Implement Platt scaling for calibration
- Backtest on 1 full NBA season of Kalshi data

### Phase 3 — Sentiment Layer (Weeks 7–9)
- Build Twitter and Reddit scrapers with entity recognition
- Integrate news article parser (newspaper3k + spaCy NER)
- Train or fine-tune sentiment classifier on sports domain text
- Implement Bayesian update mechanism combining stats prior with sentiment likelihood
- Source credibility weighting system

### Phase 4 — Market Integration & API (Weeks 10–11)
- Build edge computation layer (model probability vs. live market price)
- Signal tier classification and alert webhook system
- FastAPI server with all v1 endpoints
- Docker compose setup for full local development environment

### Phase 5 — Dashboard & Calibration Tracking (Week 12)
- Next.js dashboard: market list, signal explorer, edge report
- Calibration chart: reliability diagram showing predicted vs. actual frequencies
- SHAP feature decomposition view per market
- Documentation and internal API reference

---

## 11. Risks & Mitigations

| Risk | Description | Mitigation |
|---|---|---|
| API access restrictions | Twitter API costs have risen sharply; Reddit tightened API access in 2023 | Use nitter mirrors, RSS feeds, and web scraping as fallbacks; budget for API tiers |
| Overfitting to recent data | A model trained on recent seasons may fail when conditions change (rule changes, team changes) | Use rolling cross-validation; explicit train/test splits by season |
| Model-market circularity | If the model is widely used, it can move markets and eliminate its own edge | Not a concern at v1 scale; note this as a v3 risk |
| Calibration decay | Model accuracy degrades over time without retraining | Automated weekly retraining jobs triggered by Airflow; calibration dashboard monitoring |
| Data licensing | Some stats providers restrict commercial use of scraped data | Use official public APIs where possible (NBA Stats API, Kalshi API); document data sources |
| Regulatory uncertainty | Prediction market regulations are evolving rapidly | Scope v1 to research/analysis tooling only; do not build auto-execution without legal review |

---

## 12. Success Metrics

### 12.1 Model Quality
- Brier Score < 0.15 on held-out test markets (lower is better; random baseline = 0.25)
- Calibration error < 5% across all probability buckets
- Positive log-loss improvement over a naive baseline (market price used as the forecast)

### 12.2 Signal Quality
- Positive expected value on paper trades using Kelly-sized positions over a 3-month window
- Strong Edge tier (≥ 10% edge) resolving correctly at >60% rate
- Sentiment layer demonstrably improves calibration vs. stats-only baseline (A/B comparison)

### 12.3 System Reliability
- Data ingestion pipelines running with <1% error rate
- Market signals refreshed within 5 minutes of a live market price change
- API p99 response time < 500ms

---

## 13. Open Questions

- Which sentiment sources provide the highest lift? Requires an ablation study in Phase 3.
- What is the minimum liquidity threshold for a market to be worth covering? Thin markets have high slippage.
- Should the model produce a single probability or a distribution over possible outcomes?
- What is the right retraining cadence? Weekly seems right for sports; may differ for political markets.
- Is there a market for licensing this as a data product to quant firms, similar to how AfterQuery licenses eval data to AI labs?

---

## 14. Appendix — Key Quantitative Concepts

### Bayesian Updating
P(outcome | evidence) ∝ P(evidence | outcome) × P(outcome)

The prior P(outcome) comes from historical stats. The likelihood P(evidence | outcome) comes from the sentiment layer. The posterior is the updated market probability.

### Kelly Criterion
f* = (bp - q) / b

Where b = odds received, p = model probability of winning, q = 1 - p. This gives the fraction of bankroll to wager to maximize long-run growth. Always use fractional Kelly (0.25x to 0.5x) to account for model uncertainty.

### Brier Score
BS = (1/N) × Σ(forecast_i - outcome_i)²

Ranges from 0 (perfect) to 1 (perfectly wrong). A market price used as the forecast gives a useful baseline to beat. A skilled model should consistently score below the market baseline.

### Calibration
A model is well-calibrated if, across all predictions made at 70% confidence, approximately 70% of those events actually occurred. Platt scaling and isotonic regression are the standard post-hoc calibration techniques applied after model training.

---

*Alpha Edge — Product Requirements Document v1.0 — Confidential*
