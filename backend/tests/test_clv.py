from types import SimpleNamespace

from alpha_edge.model import clv


def sig(market_p: float, model_p: float):
    return SimpleNamespace(market_price=market_p, model_probability=model_p)


def test_none_for_single_signal():
    assert clv.clv_for_signals([sig(0.5, 0.6)]) is None


def test_none_when_no_actionable_edge():
    assert clv.clv_for_signals([sig(0.5, 0.51), sig(0.5, 0.51)], min_edge=0.03) is None


def test_positive_clv_when_line_moves_toward_yes_bet():
    # model favors YES (0.60 > 0.54 market); market closes higher (0.62) → beat close
    r = clv.clv_for_signals([sig(0.54, 0.60), sig(0.62, 0.60)])
    assert r is not None and r.direction == 1 and r.beat_close is True
    assert r.clv_pp == 8.0


def test_negative_clv_when_line_moves_against():
    r = clv.clv_for_signals([sig(0.54, 0.60), sig(0.50, 0.60)])
    assert r.direction == 1 and r.beat_close is False and r.clv_pp == -4.0


def test_no_side_beats_close_when_price_drops():
    # model favors NO (0.40 < 0.54 market); market closes lower (0.48) → beat close
    r = clv.clv_for_signals([sig(0.54, 0.40), sig(0.48, 0.40)])
    assert r.direction == -1 and r.beat_close is True and r.clv_pp == 6.0


def test_brier_score():
    assert clv.brier_score(1.0, True) == 0.0
    assert clv.brier_score(0.0, True) == 1.0
    assert abs(clv.brier_score(0.7, False) - 0.49) < 1e-9
