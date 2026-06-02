from alpha_edge.model.predict import _monte_carlo_credible_interval


def test_monte_carlo_credible_interval_bounds() -> None:
    low, high = _monte_carlo_credible_interval(0.0, 0.75, samples=2000)

    assert 0.0 <= low < high <= 1.0
    assert low < 0.5 < high
