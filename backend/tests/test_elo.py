from datetime import datetime, timezone
from types import SimpleNamespace

from alpha_edge.model import elo, elo_ratings


def test_neutral_court_is_symmetric():
    assert elo.win_probability(1500, 1500, neutral=True) == 0.5


def test_home_advantage_helps_home():
    assert elo.win_probability(1500, 1500) > 0.5
    assert round(elo.win_probability(1500, 1500), 2) == 0.64  # +100 Elo HCA


def test_higher_rating_is_favored():
    assert elo.win_probability(1700, 1500) > elo.win_probability(1500, 1500)


def test_update_is_zero_sum_and_winner_gains():
    new_w, new_l = elo.update(1500, 1500, margin=10, winner_was_home=True)
    assert new_w > 1500 and new_l < 1500
    assert round(new_w + new_l, 6) == 3000.0  # zero-sum


def test_prob_for_market_parses_ticker(monkeypatch):
    # Warm, non-empty ratings so prob_for_market's ensure_fresh() is a no-op (no network).
    monkeypatch.setattr(elo_ratings, "_ratings", {"NYK": 1900.0, "SAS": 1800.0})
    monkeypatch.setattr(elo_ratings, "_built_at", datetime.now(timezone.utc))

    # Ticker matchup SASNYK = away SAS @ home NYK; suffix is the YES team.
    yes_nyk = SimpleNamespace(external_id="kalshi:KXNBAGAME-26JUN08SASNYK-NYK")
    yes_sas = SimpleNamespace(external_id="kalshi:KXNBAGAME-26JUN08SASNYK-SAS")
    p_nyk = elo_ratings.prob_for_market(yes_nyk)
    p_sas = elo_ratings.prob_for_market(yes_sas)

    assert p_nyk is not None and p_nyk > 0.5  # higher-rated home team favored
    assert round(p_nyk + p_sas, 6) == 1.0     # the two sides are complementary


def test_prob_for_market_non_nba_is_none():
    poly = SimpleNamespace(external_id="poly:12345")
    assert elo_ratings.prob_for_market(poly) is None
