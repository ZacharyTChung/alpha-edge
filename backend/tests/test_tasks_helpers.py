from alpha_edge.workers.tasks import _dedupe_candidates


def test_dedupe_candidates_keeps_most_credible_copy() -> None:
    candidates = [
        {"text": "Same story", "base_credibility": 0.2, "source_key": "news:a"},
        {"text": "same story  ", "base_credibility": 0.8, "source_key": "news:b"},
        {"text": "Different story", "base_credibility": 0.4, "source_key": "news:c"},
    ]

    deduped = _dedupe_candidates(candidates)

    assert len(deduped) == 2
    assert deduped[0]["source_key"] == "news:b"
    assert deduped[1]["source_key"] == "news:c"
