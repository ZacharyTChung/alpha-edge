"""Model training entrypoint — logistic regression + XGBoost baseline.

Phase 2: train on historical NBA market outcomes, save artifacts to MODELS_DIR.
"""
from __future__ import annotations

from pathlib import Path

MODELS_DIR = Path("models")


def train_baseline(season: str) -> None:
    raise NotImplementedError("Implement in Phase 2: load features, fit, persist")


def train_xgboost(season: str) -> None:
    raise NotImplementedError("Implement in Phase 2")
