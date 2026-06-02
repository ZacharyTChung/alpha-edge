from types import SimpleNamespace

from alpha_edge.db.models import SentimentSource
from alpha_edge.model.predict import _source_key


def test_source_key_extracts_known_hosts() -> None:
    assert (
        _source_key(
            SimpleNamespace(
                source=SentimentSource.NEWS,
                source_url="https://www.rotowire.com/basketball/article",
                entity="",
            )
        )
        == "news:rotowire"
    )

    assert (
        _source_key(
            SimpleNamespace(
                source=SentimentSource.REDDIT,
                source_url="https://www.reddit.com/r/nba/comments/abc123",
                entity="",
            )
        )
        == "reddit:nba"
    )
