import pytest

from alpha_edge.model.bayesian import bayes_update, from_log_odds, log_odds


def test_bayes_update_neutral() -> None:
    assert bayes_update(0.5, 1.0) == pytest.approx(0.5)


def test_bayes_update_supports() -> None:
    posterior = bayes_update(0.5, 3.0)
    assert posterior > 0.5


def test_log_odds_roundtrip() -> None:
    p = 0.37
    assert from_log_odds(log_odds(p)) == pytest.approx(p)


def test_invalid_prior() -> None:
    with pytest.raises(ValueError):
        bayes_update(0.0, 2.0)
