from __future__ import annotations

import math

import pytest

from robo_evals.stats import wilson_interval, z_for_confidence


def test_z_for_95_percent() -> None:
    assert z_for_confidence(0.95) == pytest.approx(1.959964, abs=1e-6)


@pytest.mark.parametrize(
    ("k", "n", "low", "high"),
    [
        # Reference values from the closed-form Wilson score interval, z = 1.959964.
        (5, 10, 0.236593, 0.763407),
        (0, 10, 0.0, 0.277533),
        (10, 10, 0.722467, 1.0),
        (81, 100, 0.722212, 0.874852),
        (1, 20, 0.008881, 0.236131),
    ],
)
def test_wilson_matches_reference(k: int, n: int, low: float, high: float) -> None:
    lo, hi = wilson_interval(k, n)
    assert lo == pytest.approx(low, abs=5e-4)
    assert hi == pytest.approx(high, abs=5e-4)


def test_wilson_matches_formula() -> None:
    k, n, z = 7, 23, z_for_confidence(0.9)
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z / (1 + z * z / n) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    assert wilson_interval(k, n, 0.9) == pytest.approx((center - half, center + half))


def test_interval_contains_estimate_and_narrows_with_n() -> None:
    widths = []
    for n in (10, 100, 1000):
        lo, hi = wilson_interval(n // 2, n)
        assert lo < 0.5 < hi
        widths.append(hi - lo)
    assert widths == sorted(widths, reverse=True)


def test_higher_confidence_is_wider() -> None:
    lo90, hi90 = wilson_interval(30, 50, 0.90)
    lo99, hi99 = wilson_interval(30, 50, 0.99)
    assert lo99 < lo90
    assert hi99 > hi90


def test_zero_trials_is_uninformative() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)


@pytest.mark.parametrize(("k", "n"), [(-1, 5), (6, 5), (0, -1)])
def test_invalid_counts(k: int, n: int) -> None:
    with pytest.raises(ValueError, match="successes"):
        wilson_interval(k, n)


@pytest.mark.parametrize("conf", [0.0, 1.0, 1.5])
def test_invalid_confidence(conf: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        wilson_interval(1, 2, conf)
