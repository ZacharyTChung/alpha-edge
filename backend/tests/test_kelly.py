import pytest

from alpha_edge.model.kelly import kelly_fraction


def test_kelly_positive_edge() -> None:
    f = kelly_fraction(probability=0.6, market_price=0.5, fraction=1.0)
    assert f == pytest.approx(0.2, rel=1e-3)


def test_kelly_no_edge_clamps_to_zero() -> None:
    assert kelly_fraction(probability=0.4, market_price=0.5) == 0.0


def test_kelly_fractional_scaling() -> None:
    full = kelly_fraction(probability=0.6, market_price=0.5, fraction=1.0)
    quarter = kelly_fraction(probability=0.6, market_price=0.5, fraction=0.25)
    assert quarter == pytest.approx(0.25 * full)


def test_kelly_invalid_price() -> None:
    with pytest.raises(ValueError):
        kelly_fraction(probability=0.6, market_price=0.0)
