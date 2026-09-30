"""A minimal custom policy for the ``reach`` task.

Run it with::

    robo-evals run --policy examples/my_policy.py:ReachPolicy --tasks reach
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


class ReachPolicy:
    """Moves the gripper straight toward ``goal_pos`` with a proportional gain."""

    def __init__(self, gain: float = 30.0) -> None:
        self.gain = gain

    def reset(self, task: str, seed: int) -> None:
        if task != "reach":
            raise ValueError("ReachPolicy only knows the reach task")

    def __call__(self, obs: Mapping[str, Any]) -> list[float]:
        delta = np.asarray(obs["goal_pos"]) - np.asarray(obs["ee_pos"])
        move = np.clip(self.gain * delta, -1.0, 1.0)
        return [*move.tolist(), -1.0]
