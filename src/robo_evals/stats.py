"""Binomial confidence intervals for success rates."""

from __future__ import annotations

import math
from statistics import NormalDist


def z_for_confidence(confidence: float) -> float:
    """Returns the two-sided standard normal quantile for ``confidence``."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return NormalDist().inv_cdf(0.5 + confidence / 2.0)


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Computes the Wilson score interval for a binomial proportion.

    Unlike the normal (Wald) interval, the Wilson interval stays inside
    ``[0, 1]`` and remains informative at 0 or ``trials`` successes, which is
    common when a policy fails or solves a task on every episode.

    Returns:
        ``(low, high)``. With zero trials, returns ``(0.0, 1.0)``.
    """
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError(f"need 0 <= successes <= trials, got {successes}/{trials}")
    if trials == 0:
        return 0.0, 1.0
    z = z_for_confidence(confidence)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denom
    half = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials)) / denom
    low = 0.0 if successes == 0 else max(0.0, center - half)
    high = 1.0 if successes == trials else min(1.0, center + half)
    return low, high
