"""Uniform random baseline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from robo_evals.env import ACTION_DIM


class RandomPolicy:
    """Samples every action uniformly from ``[-1, 1]``.

    The generator is reseeded from the episode seed in ``reset``, so random
    rollouts are as reproducible as any other policy.
    """

    def __init__(self) -> None:
        self._rng = np.random.default_rng(0)

    def reset(self, task: str, seed: int) -> None:
        self._rng = np.random.default_rng([seed, 0x5EED])

    def __call__(self, obs: Mapping[str, Any]) -> NDArray[np.float64]:
        return self._rng.uniform(-1.0, 1.0, size=ACTION_DIM)
