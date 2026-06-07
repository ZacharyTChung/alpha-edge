"""Pipeline tasks. Run from the /admin/refresh endpoint or a future scheduler."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from alpha_edge.config import get_settings
from alpha_edge.db.models import (
    Category,
    Market,
    SentimentEvent,
    SentimentLabel,
    SentimentSource,
)
from alpha_edge.db.session import SessionLocal
from alpha_edge.ingestion import basketball_ref as bbref_mod
from alpha_edge.ingestion import kalshi as kalshi_client
from alpha_edge.ingestion import polymarket as poly_client
from alpha_edge.model import elo_ratings
from alpha_edge.model.predict import predict_market, write_signal
from alpha_edge.sentiment import bluesky as bsky_mod
from alpha_edge.sentiment import hn as hn_mod
from alpha_edge.sentiment import llm as llm_mod
from alpha_edge.sentiment import news as news_mod
from alpha_edge.sentiment import nlp as nlp_mod
from alpha_edge.sentiment import reddit as reddit_mod
from alpha_edge.sentiment import twitter as twitter_mod
from alpha_edge.sentiment import x_syndication as xs_mod
from alpha_edge.sentiment.credibility import credibility_for

_GATE_STOPWORDS = {
    "game", "winner", "series", "match", "season", "league", "final", "finals",
    "playoff", "playoffs", "today", "tonight", "team", "over", "under",
    "yes", "no", "the", "and", "for", "will",
}


def _parse_published(value) -> datetime | None:
    """Best-effort parse of a source publish date into an aware UTC datetime.

    Handles RSS strings, ISO-8601 (Bluesky/HN), Twitter's format, and epoch
    floats (Reddit ``created_utc``). Returns None if missing or unparseable.
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc) if value > 0 else None
    try:
        from dateutil import parser as _dateparser

        dt = _dateparser.parse(str(value))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text_matches_market(text: str, terms: list[str]) -> bool:
    """Heuristic relevance gate: the evidence must strongly reference the
    market's entities. Mirrors ``news.match_terms`` strength — >=1 multi-word
    entity, or >=2 distinct single-word entities, or >=1 long (>=7 char) single
    entity. Keeps coaching/off-topic chatter off unrelated markets in keyless
    mode, where there is no LLM relevance score.
    """
    hay = (text or "").lower()
    multi = [t.lower() for t in terms if " " in t]
    if any(t in hay for t in multi):
        return True
    single = [
        t.lower() for t in terms
        if " " not in t and len(t) >= 5 and t.lower() not in _GATE_STOPWORDS
    ]
    hits = [t for t in single if t in hay]
    return len(hits) >= 2 or any(len(t) >= 7 for t in hits)


def _gate_candidates(candidates: list[dict], terms: list[str], max_age_days: int) -> list[dict]:
    """Drop evidence that is stale (published before the cutoff) or not actually
    about this market. Undated candidates pass the recency check (can't assess)
    but must still pass the relevance check.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    out: list[dict] = []
    for c in candidates:
        pub = c.get("published_at")
        if pub is not None and pub < cutoff:
            continue
        if not _text_matches_market(c.get("text", ""), terms):
            continue
        out.append(c)
    return out


@dataclass
class RefreshSummary:
    polymarket_markets: int = 0
    kalshi_markets: int = 0
    sentiment_events: int = 0
    signals_written: int = 0
    reddit_enabled: bool = False
    twitter_enabled: bool = False
    bluesky_events: int = 0
    google_news_events: int = 0
    rotowire_events: int = 0
    x_syndication_events: int = 0
    hn_events: int = 0
    llm_enabled: bool = False
    llm_classifications: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def to_dict(self) -> dict:
        return {
            "polymarket_markets": self.polymarket_markets,
            "kalshi_markets": self.kalshi_markets,
            "sentiment_events": self.sentiment_events,
            "signals_written": self.signals_written,
            "reddit_enabled": self.reddit_enabled,
            "twitter_enabled": self.twitter_enabled,
            "bluesky_events": self.bluesky_events,
            "google_news_events": self.google_news_events,
            "rotowire_events": self.rotowire_events,
            "x_syndication_events": self.x_syndication_events,
            "hn_events": self.hn_events,
            "llm_enabled": self.llm_enabled,
            "llm_classifications": self.llm_classifications,
            "errors": self.errors or [],
        }


def _upsert_market(db: Session, market_row: Market, latest_price: float) -> tuple[Market, float]:
    existing = db.scalar(
        select(Market).where(Market.external_id == market_row.external_id)
    )
    if existing is None:
        db.add(market_row)
        db.flush()
        return market_row, latest_price
    existing.question_text = market_row.question_text
    existing.category = market_row.category
    existing.close_time = market_row.close_time
    existing.resolution_criteria = market_row.resolution_criteria
    existing.liquidity = market_row.liquidity
    return existing, latest_price


def poll_polymarket_markets(
    db: Session,
    summary: RefreshSummary,
    limit: int = 50,
) -> list[tuple[Market, float]]:
    items = poly_client.fetch_active_markets(limit=limit, min_volume=100.0)
    out: list[tuple[Market, float]] = []
    for item in items:
        try:
            row = poly_client.to_market_row(item)
            market, price = _upsert_market(db, row, item["yes_price"])
            out.append((market, price))
            summary.polymarket_markets += 1
        except Exception as e:
            summary.errors.append(f"polymarket upsert: {e}")
    return out


def poll_kalshi_markets(
    db: Session,
    summary: RefreshSummary,
    limit: int = 50,
) -> list[tuple[Market, float]]:
    elo_ratings.ensure_fresh()  # rebuild team Elo (cached ~6h) before predictions
    items = kalshi_client.fetch_active_markets(limit=limit)
    out: list[tuple[Market, float]] = []
    for item in items:
        try:
            row = kalshi_client.to_market_row(item)
            market, price = _upsert_market(db, row, item["yes_price"])
            out.append((market, price))
            summary.kalshi_markets += 1
        except Exception as e:
            summary.errors.append(f"kalshi upsert: {e}")
    return out


def _persist_sentiment(
    db: Session,
    market: Market,
    text: str,
    source: SentimentSource,
    source_url: str,
    entity: str,
    source_key: str,
) -> bool:
    classified = nlp_mod.classify(text)
    label_map = {
        "positive": SentimentLabel.POSITIVE,
        "negative": SentimentLabel.NEGATIVE,
        "neutral": SentimentLabel.NEUTRAL,
    }
    db.add(
        SentimentEvent(
            market_id=market.id,
            source=source,
            source_url=source_url[:500] if source_url else "",
            entity=entity[:200],
            raw_text=text[:2000],
            sentiment=label_map[classified.sentiment.value],
            credibility_weight=credibility_for(source_key),
            novelty_score=1.0,
        )
    )
    return True


def _persist_classified(
    db: Session,
    market: Market,
    text: str,
    source: SentimentSource,
    source_url: str,
    entity: str,
    sentiment_label: str,
    credibility: float,
    novelty: float,
    relevance: float = 1.0,
    reasoning: str | None = None,
    detected_at: datetime | None = None,
) -> None:
    label_map = {
        "positive": SentimentLabel.POSITIVE,
        "negative": SentimentLabel.NEGATIVE,
        "neutral": SentimentLabel.NEUTRAL,
    }
    event = SentimentEvent(
        market_id=market.id,
        source=source,
        source_url=(source_url or "")[:500],
        entity=(entity or "")[:200],
        raw_text=(text or "")[:2000],
        sentiment=label_map.get(sentiment_label, SentimentLabel.NEUTRAL),
        credibility_weight=max(0.0, min(1.0, credibility)),
        novelty_score=max(0.0, min(1.0, novelty)),
        relevance_score=max(0.0, min(1.0, relevance)),
        llm_reasoning=(reasoning or None),
    )
    if detected_at is not None:
        event.detected_at = detected_at
    db.add(event)


def _build_search_query(terms: list[str]) -> str:
    """Compose a search query from market entity terms.

    Multi-word terms are quoted to require exact phrase; single-word terms are
    OR'd. Capped at 4 terms — beyond that Google News and Bluesky start
    behaving like fuzzy match and precision tanks.
    """
    multi = [f'"{t}"' for t in terms if " " in t][:2]
    single = [t for t in terms if " " not in t and len(t) >= 5][:3]
    parts = multi + single
    return " ".join(parts)


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    """Collapse exact/near-exact duplicate snippets before classification.

    When the same syndicated article appears from multiple feeds, we keep the
    most credible copy and drop the rest to avoid overweighting repeated text.
    """
    best_by_text: dict[str, dict] = {}
    order: list[str] = []
    for candidate in candidates:
        text = " ".join((candidate.get("text") or "").split()).strip().lower()
        if not text:
            continue
        existing = best_by_text.get(text)
        if existing is None:
            best_by_text[text] = candidate
            order.append(text)
            continue
        if float(candidate.get("base_credibility", 0.0)) > float(
            existing.get("base_credibility", 0.0)
        ):
            best_by_text[text] = candidate
    return [best_by_text[key] for key in order]


def scrape_sentiment(
    db: Session,
    summary: RefreshSummary,
    markets: list[tuple[Market, float]],
) -> None:
    """Per-market: collect candidate texts from Google News + Bluesky + Reddit +
    X-syndication + broad RSS, then either send the whole batch to Claude for
    relevance-aware classification, or fall back to VADER per text."""
    if not markets:
        return

    # Broad-corpus pulls — done once per refresh, matched against many markets.
    broad_news = news_mod.fetch_all_default()
    try:
        broad_news.extend(news_mod.fetch_espn_news())
    except Exception as e:
        summary.errors.append(f"espn news: {e}")
    reddit_docs: list = []
    summary.reddit_enabled = reddit_mod.is_configured()
    if summary.reddit_enabled:
        try:
            reddit_docs = reddit_mod.fetch_default(limit_per_sub=40)
        except Exception as e:
            summary.errors.append(f"reddit fetch: {e}")
    summary.twitter_enabled = twitter_mod.is_configured()
    try:
        x_posts = xs_mod.fetch_default(max_age_days=get_settings().sentiment_max_age_days)
    except Exception as e:
        summary.errors.append(f"x_syndication: {e}")
        x_posts = []
    summary.llm_enabled = llm_mod.is_configured()

    for market, _price in markets:
        terms = nlp_mod.entity_terms(market.question_text)
        if not terms:
            continue
        query = _build_search_query(terms)

        # Build candidates: list of dicts with all metadata, classified later in batch.
        candidates: list[dict] = []

        try:
            for doc in news_mod.fetch_google_news_multi(terms, per_query=3):
                candidates.append({
                    "text": f"{doc.title}. {doc.body}",
                    "source_enum": SentimentSource.NEWS,
                    "url": doc.url,
                    "entity": ", ".join(doc.matched_terms),
                    "source_key": doc.source,
                    "base_credibility": credibility_for(doc.source),
                    "published_at": _parse_published(doc.publish_date),
                })
                summary.google_news_events += 1
        except Exception as e:
            summary.errors.append(f"google_news {market.id}: {e}")

        if query:
            try:
                for post in list(bsky_mod.search_posts(query, limit=8))[:4]:
                    candidates.append({
                        "text": post.text,
                        "source_enum": SentimentSource.TWITTER,
                        "url": post.url,
                        "entity": post.handle,
                        "source_key": f"bluesky:{post.handle}",
                        "base_credibility": bsky_mod.credibility_for_post(post),
                        "published_at": _parse_published(post.created_at),
                    })
                    summary.bluesky_events += 1
            except Exception as e:
                summary.errors.append(f"bluesky {market.id}: {e}")

        for doc in news_mod.match_terms(broad_news, terms)[:5]:
            candidates.append({
                "text": f"{doc.title}. {doc.body}",
                "source_enum": SentimentSource.NEWS,
                "url": doc.url,
                "entity": ", ".join(doc.matched_terms),
                "source_key": doc.source,
                "base_credibility": credibility_for(doc.source),
                "published_at": _parse_published(doc.publish_date),
            })
            if doc.source == "news:rotowire":
                summary.rotowire_events += 1

        for doc in reddit_mod.match_terms(reddit_docs, terms)[:4]:
            src_key = f"reddit:{doc.subreddit}"
            candidates.append({
                "text": f"{doc.title}. {doc.body}",
                "source_enum": SentimentSource.REDDIT,
                "url": doc.permalink,
                "entity": ", ".join(doc.matched_terms),
                "source_key": src_key,
                "base_credibility": credibility_for(src_key),
                "published_at": _parse_published(doc.created_utc),
            })

        if summary.twitter_enabled and query:
            for doc in list(twitter_mod.search_recent(query, max_results=10))[:4]:
                candidates.append({
                    "text": doc.text,
                    "source_enum": SentimentSource.TWITTER,
                    "url": doc.url,
                    "entity": doc.author,
                    "source_key": f"twitter:{doc.author}",
                    "base_credibility": credibility_for(f"twitter:{doc.author}"),
                })

        # Hacker News for finance/politics markets — sports markets skip this
        if market.category in (Category.FINANCE, Category.POLITICS) and query:
            try:
                for doc in list(hn_mod.search_hn(query, hits=5))[:4]:
                    candidates.append({
                        "text": doc.title,
                        "source_enum": SentimentSource.NEWS,
                        "url": doc.url,
                        "entity": doc.author,
                        "source_key": "news:hn",
                        "base_credibility": hn_mod.credibility_for_post(doc),
                        "published_at": _parse_published(doc.created_at),
                    })
                    summary.hn_events += 1
            except Exception as e:
                summary.errors.append(f"hn {market.id}: {e}")

        for post in xs_mod.match_terms(x_posts, terms)[:4]:
            candidates.append({
                "text": post.text,
                "source_enum": SentimentSource.TWITTER,
                "url": post.url,
                "entity": post.handle,
                "source_key": f"x:{post.handle}",
                "base_credibility": xs_mod.credibility_for_handle(post.handle),
                "published_at": _parse_published(post.created_at),
            })
            summary.x_syndication_events += 1

        candidates = _dedupe_candidates(candidates)
        candidates = _gate_candidates(candidates, terms, get_settings().sentiment_max_age_days)
        if not candidates:
            continue

        from alpha_edge.config import get_settings as _gs
        min_liq = _gs().llm_min_liquidity
        eligible_for_llm = summary.llm_enabled and float(market.liquidity or 0.0) >= min_liq
        if eligible_for_llm:
            try:
                stats_context = bbref_mod.market_stats_context(market.question_text)
                classifications = llm_mod.classify_for_market(
                    market_question=market.question_text,
                    texts=[c["text"] for c in candidates],
                    sources=[c["source_key"] for c in candidates],
                    stats_context=stats_context,
                )
            except Exception as e:
                summary.errors.append(f"llm {market.id}: {e}")
                classifications = []
        else:
            classifications = []

        if classifications and len(classifications) == len(candidates):
            summary.llm_classifications += len(classifications)
            for c, cls in zip(candidates, classifications, strict=True):
                if cls.relevance < 0.2:
                    continue  # LLM said this isn't actually about the market
                # Final credibility = source baseline scaled by LLM confidence.
                final_cred = c["base_credibility"] * (0.5 + 0.5 * cls.confidence)
                _persist_classified(
                    db, market, c["text"], c["source_enum"], c["url"], c["entity"],
                    cls.sentiment, final_cred, novelty=1.0,
                    relevance=cls.relevance, reasoning=cls.reasoning,
                    detected_at=c.get("published_at"),
                )
                summary.sentiment_events += 1
        else:
            # VADER fallback (or LLM disabled / skipped due to low liquidity)
            for c in candidates:
                classified = nlp_mod.classify(c["text"])
                _persist_classified(
                    db, market, c["text"], c["source_enum"], c["url"], c["entity"],
                    classified.sentiment.value, c["base_credibility"], novelty=1.0,
                    detected_at=c.get("published_at"),
                )
                summary.sentiment_events += 1


def regenerate_signals(
    db: Session,
    summary: RefreshSummary,
    markets: list[tuple[Market, float]],
) -> None:
    for market, price in markets:
        try:
            pred = predict_market(db, market, price)
            write_signal(db, market, price, pred)
            summary.signals_written += 1
        except Exception as e:
            summary.errors.append(f"signal {market.id}: {e}")


def refresh_priority(
    polymarket_limit: int = 12,
    kalshi_limit: int = 20,
    min_liquidity: float = 1000.0,
) -> RefreshSummary:
    """Sub-30s refresh: sports markets only, high-liquidity, abbreviated sentiment.

    Skips broad RSS, X syndication (rate-limited), and HN (no sports coverage).
    Uses LLM classification on candidates that DO appear (Google News + Bluesky +
    Reddit only).
    """
    summary = RefreshSummary(errors=[])
    db = SessionLocal()
    try:
        markets: list[tuple[Market, float]] = []
        try:
            markets += poll_polymarket_markets(db, summary, limit=polymarket_limit)
        except Exception as e:
            summary.errors.append(f"polymarket poll: {e}")
        try:
            markets += poll_kalshi_markets(db, summary, limit=kalshi_limit)
        except Exception as e:
            summary.errors.append(f"kalshi poll: {e}")

        # Filter to sports + liquid only
        markets = [
            (m, p) for (m, p) in markets
            if m.category == Category.SPORTS and float(m.liquidity or 0.0) >= min_liquidity
        ]
        db.flush()

        try:
            scrape_sentiment_priority(db, summary, markets)
        except Exception as e:
            summary.errors.append(f"sentiment: {e}")

        regenerate_signals(db, summary, markets)
        db.commit()
    except Exception as e:
        db.rollback()
        summary.errors.append(f"priority refresh fatal: {e}")
    finally:
        db.close()
    return summary


def scrape_sentiment_priority(
    db: Session,
    summary: RefreshSummary,
    markets: list[tuple[Market, float]],
) -> None:
    """Abbreviated sentiment: per-market Google News + Bluesky + Reddit only,
    routed through the LLM. No broad RSS, no X syndication, no HN."""
    if not markets:
        return
    reddit_docs: list = []
    summary.reddit_enabled = reddit_mod.is_configured()
    if summary.reddit_enabled:
        try:
            reddit_docs = reddit_mod.fetch_default(limit_per_sub=25)
        except Exception as e:
            summary.errors.append(f"reddit fetch: {e}")
    summary.llm_enabled = llm_mod.is_configured()

    for market, _price in markets:
        terms = nlp_mod.entity_terms(market.question_text)
        if not terms:
            continue
        query = _build_search_query(terms)
        candidates: list[dict] = []

        try:
            for doc in news_mod.fetch_google_news_multi(terms, per_query=2):
                candidates.append({
                    "text": f"{doc.title}. {doc.body}",
                    "source_enum": SentimentSource.NEWS,
                    "url": doc.url,
                    "entity": ", ".join(doc.matched_terms),
                    "source_key": doc.source,
                    "base_credibility": credibility_for(doc.source),
                    "published_at": _parse_published(doc.publish_date),
                })
                summary.google_news_events += 1
        except Exception as e:
            summary.errors.append(f"google_news {market.id}: {e}")

        if query:
            try:
                for post in list(bsky_mod.search_posts(query, limit=4))[:3]:
                    candidates.append({
                        "text": post.text,
                        "source_enum": SentimentSource.TWITTER,
                        "url": post.url,
                        "entity": post.handle,
                        "source_key": f"bluesky:{post.handle}",
                        "base_credibility": bsky_mod.credibility_for_post(post),
                        "published_at": _parse_published(post.created_at),
                    })
                    summary.bluesky_events += 1
            except Exception as e:
                summary.errors.append(f"bluesky {market.id}: {e}")

        for doc in reddit_mod.match_terms(reddit_docs, terms)[:3]:
            src_key = f"reddit:{doc.subreddit}"
            candidates.append({
                "text": f"{doc.title}. {doc.body}",
                "source_enum": SentimentSource.REDDIT,
                "url": doc.permalink,
                "entity": ", ".join(doc.matched_terms),
                "source_key": src_key,
                "base_credibility": credibility_for(src_key),
                "published_at": _parse_published(doc.created_utc),
            })

        candidates = _dedupe_candidates(candidates)
        candidates = _gate_candidates(candidates, terms, get_settings().sentiment_max_age_days)
        if not candidates:
            continue

        if summary.llm_enabled:
            try:
                stats_context = bbref_mod.market_stats_context(market.question_text)
                classifications = llm_mod.classify_for_market(
                    market_question=market.question_text,
                    texts=[c["text"] for c in candidates],
                    sources=[c["source_key"] for c in candidates],
                    stats_context=stats_context,
                )
            except Exception as e:
                summary.errors.append(f"llm {market.id}: {e}")
                classifications = []
        else:
            classifications = []

        if classifications and len(classifications) == len(candidates):
            summary.llm_classifications += len(classifications)
            for c, cls in zip(candidates, classifications, strict=True):
                if cls.relevance < 0.2:
                    continue
                final_cred = c["base_credibility"] * (0.5 + 0.5 * cls.confidence)
                _persist_classified(
                    db, market, c["text"], c["source_enum"], c["url"], c["entity"],
                    cls.sentiment, final_cred, novelty=1.0,
                    relevance=cls.relevance, reasoning=cls.reasoning,
                    detected_at=c.get("published_at"),
                )
                summary.sentiment_events += 1
        else:
            for c in candidates:
                classified = nlp_mod.classify(c["text"])
                _persist_classified(
                    db, market, c["text"], c["source_enum"], c["url"], c["entity"],
                    classified.sentiment.value, c["base_credibility"], novelty=1.0,
                    detected_at=c.get("published_at"),
                )
                summary.sentiment_events += 1


def refresh_all(
    polymarket_limit: int = 30,
    kalshi_limit: int = 30,
) -> RefreshSummary:
    """Run the full pipeline once and return a JSON-serialisable summary."""
    summary = RefreshSummary(errors=[])
    db = SessionLocal()
    try:
        markets = []
        try:
            markets += poll_polymarket_markets(db, summary, limit=polymarket_limit)
        except Exception as e:
            summary.errors.append(f"polymarket poll: {e}")
        try:
            markets += poll_kalshi_markets(db, summary, limit=kalshi_limit)
        except Exception as e:
            summary.errors.append(f"kalshi poll: {e}")

        db.flush()

        try:
            scrape_sentiment(db, summary, markets)
        except Exception as e:
            summary.errors.append(f"sentiment: {e}")

        regenerate_signals(db, summary, markets)
        db.commit()
    except Exception as e:
        db.rollback()
        summary.errors.append(f"refresh fatal: {e}")
    finally:
        db.close()
    return summary


def ingest_nba_daily() -> None:
    """Phase 2: pull yesterday's NBA box scores and store as PlayerGameStats.

    Player→market resolution requires NER we haven't built yet, so this is
    parked until we have entity resolution.
    """
    raise NotImplementedError("Pending entity resolution layer")


def retrain_models() -> None:
    raise NotImplementedError("Phase 2: train regression baseline on PlayerGameStats")
