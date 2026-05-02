"""NLP processing: entity extraction, sentiment classification, claim parsing.

Pipeline (PRD section 5.2):
  1. Entity extraction (spaCy NER fine-tuned for sports entities)
  2. Sentiment classification (HF transformer)
  3. Claim extraction for injury reports
  4. Novelty detection vs. recent corpus
"""
from __future__ import annotations

from dataclasses import dataclass

from alpha_edge.db.models import SentimentLabel


@dataclass
class Entity:
    text: str
    label: str
    start: int
    end: int


@dataclass
class ClassifiedDoc:
    entities: list[Entity]
    sentiment: SentimentLabel
    sentiment_score: float
    novelty: float
    claims: list[str]


def classify(text: str) -> ClassifiedDoc:
    raise NotImplementedError("Wire spaCy NER + HF sentiment pipeline in Phase 3")


def extract_injury_claims(text: str) -> list[str]:
    raise NotImplementedError("Pattern-based extraction over NER spans in Phase 3")
