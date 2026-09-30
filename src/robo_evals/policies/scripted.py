"""A privileged scripted controller that solves every built-in task.

It reads ground-truth object positions from the observation, so it is an
upper-bound reference for the harness, not a learned policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from robo_evals.env import MAX_DELTA

OPEN = -1.0
CLOSE = 1.0


def _move(ee: NDArray[np.float64], target: NDArray[np.float64], grip: float) -> NDArray[np.float64]:
    delta = np.clip((target - ee) / MAX_DELTA, -1.0, 1.0)
    return np.concatenate([delta, [grip]])


class ScriptedPolicy:
    """Per-task state machines driven by privileged state."""

    def __init__(self) -> None:
        self.task = ""
        self.phase = "start"
        self.counter = 0

    def reset(self, task: str, seed: int) -> None:
        self.task = task
        self.phase = "start"
        self.counter = 0

    def __call__(self, obs: Mapping[str, Any]) -> NDArray[np.float64]:
        handler = getattr(self, f"_{self.task}", None)
        if handler is None:
            raise ValueError(f"scripted policy has no controller for task {self.task!r}")
        ee = np.asarray(obs["ee_pos"], dtype=np.float64)
        return np.asarray(handler(ee, obs), dtype=np.float64)

    def _goto(self, phase: str) -> None:
        self.phase = phase
        self.counter = 0

    # -- tasks ------------------------------------------------------------------------

    def _reach(self, ee: NDArray[np.float64], obs: Mapping[str, Any]) -> NDArray[np.float64]:
        return _move(ee, np.asarray(obs["goal_pos"]), OPEN)

    def _push(self, ee: NDArray[np.float64], obs: Mapping[str, Any]) -> NDArray[np.float64]:
        cube = np.asarray(obs["object_pos"])
        goal = np.asarray(obs["goal_pos"])
        to_goal = goal[:2] - cube[:2]
        direction = to_goal / max(float(np.linalg.norm(to_goal)), 1e-6)
        push_z = 0.03
        behind = cube[:2] - direction * 0.065
        rel = ee[:2] - cube[:2]
        along = float(rel @ direction)
        lateral = abs(float(rel[0] * direction[1] - rel[1] * direction[0]))

        if self.phase in ("start", "lift"):
            if ee[2] < 0.08 and np.linalg.norm(ee[:2] - behind) > 0.02:
                return _move(ee, np.array([ee[0], ee[1], 0.1]), CLOSE)
            self._goto("above")
        if self.phase == "above":
            target = np.array([behind[0], behind[1], 0.1])
            if np.linalg.norm(ee[:2] - behind) < 0.01:
                self._goto("descend")
            else:
                return _move(ee, target, CLOSE)
        if self.phase == "descend":
            target = np.array([behind[0], behind[1], push_z])
            if abs(ee[2] - push_z) < 0.01:
                self._goto("push")
            else:
                return _move(ee, target, CLOSE)
        # push: drive through the cube along the cube-to-goal line, steering back onto it.
        if lateral > 0.025 or along > -0.02:
            self._goto("lift")
            return _move(ee, np.array([ee[0], ee[1], 0.1]), CLOSE)
        line_point = cube[:2] - direction * 0.045
        target_xy = line_point + direction * 0.04
        return _move(ee, np.array([target_xy[0], target_xy[1], push_z]), CLOSE)

    def _pick(
        self, ee: NDArray[np.float64], cube: NDArray[np.float64], gripper: float
    ) -> NDArray[np.float64] | None:
        """Runs the grasp phases. Returns ``None`` once the cube is held."""
        if self.phase == "start":
            self._goto("above")
        if self.phase == "above":
            target = cube + np.array([0.0, 0.0, 0.08])
            if np.linalg.norm(ee[:2] - cube[:2]) < 0.008 and abs(ee[2] - target[2]) < 0.02:
                self._goto("descend")
            else:
                return _move(ee, target, OPEN)
        if self.phase == "descend":
            target = cube + np.array([0.0, 0.0, 0.003])
            if np.linalg.norm(ee - target) < 0.008:
                self._goto("grasp")
            else:
                return _move(ee, target, OPEN)
        if self.phase == "grasp":
            self.counter += 1
            if self.counter < 8:
                return _move(ee, cube + np.array([0.0, 0.0, 0.003]), CLOSE)
            self._goto("carry")
        # Holding: fall back to regrasping if the cube slipped out.
        if np.linalg.norm(ee - cube) > 0.03 or gripper < 0.05:
            self._goto("above")
            return _move(ee, ee + np.array([0.0, 0.0, 0.05]), OPEN)
        return None

    def _pick_place(self, ee: NDArray[np.float64], obs: Mapping[str, Any]) -> NDArray[np.float64]:
        cube = np.asarray(obs["object_pos"])
        action = self._pick(ee, cube, float(obs["gripper"][0]))
        if action is not None:
            return action
        # Aim the cube (not the gripper) at the goal to cancel any grasp offset.
        goal = np.asarray(obs["goal_pos"])
        return _move(ee, goal + (ee - cube), CLOSE)

    def _stack(self, ee: NDArray[np.float64], obs: Mapping[str, Any]) -> NDArray[np.float64]:
        cube = np.asarray(obs["object_pos"])
        base = np.asarray(obs["target_pos"])
        if self.phase in ("release", "retreat"):
            self.counter += 1
            if self.phase == "release" and self.counter > 6:
                self._goto("retreat")
            return _move(
                ee, np.array([ee[0], ee[1], ee[2] + 0.02]) if self.phase == "retreat" else ee, OPEN
            )
        action = self._pick(ee, cube, float(obs["gripper"][0]))
        if action is not None:
            return action
        offset = ee - cube
        above = base + np.array([0.0, 0.0, 0.08])
        place = base + np.array([0.0, 0.0, 0.042])
        if self.phase == "carry":
            if np.linalg.norm(cube[:2] - base[:2]) < 0.006 and abs(cube[2] - above[2]) < 0.02:
                self._goto("lower")
            else:
                return _move(ee, above + offset, CLOSE)
        if np.linalg.norm(cube - place) < 0.005:
            self._goto("release")
            return _move(ee, ee, OPEN)
        return _move(ee, place + offset, CLOSE)

    def _drawer(self, ee: NDArray[np.float64], obs: Mapping[str, Any]) -> NDArray[np.float64]:
        handle = np.asarray(obs["handle_pos"])
        pre = handle + np.array([-0.07, 0.0, 0.0])
        if self.phase == "start":
            self._goto("pregrasp")
        if self.phase == "pregrasp":
            if np.linalg.norm(ee - pre) < 0.01:
                self._goto("approach")
            else:
                # Stay high until the gripper is in front of the handle.
                target = pre if ee[0] < pre[0] + 0.02 else np.array([pre[0], pre[1], pre[2] + 0.1])
                return _move(ee, target, OPEN)
        if self.phase == "approach":
            if np.linalg.norm(ee - handle) < 0.006:
                self._goto("grasp")
            else:
                return _move(ee, handle, OPEN)
        if self.phase == "grasp":
            self.counter += 1
            if self.counter < 8:
                return _move(ee, handle, CLOSE)
            self._goto("pull")
        if np.linalg.norm(ee - handle) > 0.03:
            self._goto("pregrasp")
            return _move(ee, ee, OPEN)
        return _move(ee, handle + np.array([-0.05, 0.0, 0.0]), CLOSE)
