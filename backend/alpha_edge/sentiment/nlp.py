"""NLP processing: VADER sentiment + lightweight entity extraction.

Phase 3 of the PRD calls for spaCy NER + a HuggingFace transformer. We ship a
v1 with VADER (rule-based, ~50 KB) so the system runs without GPU-class deps.
The interface here is stable; swapping in a transformer later is a one-file
change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from alpha_edge.db.models import SentimentLabel

_analyzer = SentimentIntensityAnalyzer()
_TITLECASE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
_INJURY_PATS = [
    r"\b(out|questionable|doubtful|probable|day-?to-?day|gtd)\b",
    r"\b(injur(?:y|ed)|sprain|strain|tear|surger(?:y|ies))\b",
    r"\b(ruled out|will (?:not )?play|did not (?:practice|play))\b",
]


@dataclass
class Entity:
    text: str
    label: str
    start: int
    end: int


@dataclass
class ClassifiedDoc:
    text: str
    entities: list[Entity]
    sentiment: SentimentLabel
    sentiment_score: float
    novelty: float = 1.0
    claims: list[str] = field(default_factory=list)


def _label_from_compound(c: float) -> SentimentLabel:
    if c >= 0.05:
        return SentimentLabel.POSITIVE
    if c <= -0.05:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.NEUTRAL


def classify(text: str) -> ClassifiedDoc:
    text = text or ""
    scores = _analyzer.polarity_scores(text)
    compound = float(scores.get("compound", 0.0))
    entities: list[Entity] = []
    for m in _TITLECASE.finditer(text):
        entities.append(Entity(text=m.group(1), label="ENT", start=m.start(), end=m.end()))
    return ClassifiedDoc(
        text=text,
        entities=entities,
        sentiment=_label_from_compound(compound),
        sentiment_score=compound,
        claims=extract_injury_claims(text),
    )


def extract_injury_claims(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    lower = text.lower()
    for pat in _INJURY_PATS:
        if re.search(pat, lower):
            for sent in re.split(r"(?<=[.!?])\s+", text):
                if re.search(pat, sent.lower()):
                    out.append(sent.strip()[:240])
    return list(dict.fromkeys(out))[:5]


def entity_terms(question_text: str) -> list[str]:
    """Pull rough entity strings out of a market question for keyword matching.

    Heuristic: title-case multi-word spans + capitalised single tokens longer
    than 3 chars. Good enough until we wire spaCy NER.
    """
    text = question_text or ""
    terms: list[str] = []
    for m in _TITLECASE.finditer(text):
        terms.append(m.group(1))
    for tok in re.findall(r"\b[A-Z]{3,}\b", text):
        terms.append(tok)
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        k = t.lower()
        if k in seen:
            continue
        if k in {"yes", "no", "the", "and"}:
            continue
        seen.add(k)
        out.append(t)
    return out
