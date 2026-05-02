"""Scheduled jobs.

Wire to Prefect or Airflow in Phase 1/4. Each function is a discrete task
that should be idempotent and independently re-runnable.
"""
from __future__ import annotations


def ingest_nba_daily() -> None:
    raise NotImplementedError("Phase 1: pull yesterday's box scores")


def poll_kalshi_markets() -> None:
    raise NotImplementedError("Phase 1: refresh open Kalshi markets and prices")


def poll_polymarket_markets() -> None:
    raise NotImplementedError("Phase 1: refresh open Polymarket markets and prices")


def scrape_sentiment() -> None:
    raise NotImplementedError("Phase 3: pull recent twitter/reddit/news, classify, persist")


def regenerate_signals() -> None:
    raise NotImplementedError("Phase 4: for each open market, run predict + edge, write Signal row")


def retrain_models() -> None:
    raise NotImplementedError("Phase 2: weekly retrain triggered by scheduler")
