"""The built-in task catalog and suites."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from robo_evals.env import FINGER_OPEN, Task
from robo_evals.randomization import Randomization


class Reach(Task):
    """Move the grip point within 3 cm of a target in free space."""

    name = "reach"
    xml = "reach.xml"
    instruction = "move the gripper to the green target"
    max_steps = 60
    tolerance = 0.03

    def _sample_scene(self) -> None:
        goal = self._uniform([-0.2, -0.2, 0.05], [0.2, 0.2, 0.3])
        self.model.site_pos[self.model.site("goal").id] = goal

    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        return {"goal_pos": self.site_pos("goal")}

    def is_success(self) -> bool:
        return bool(np.linalg.norm(self.ee_pos - self.site_pos("goal")) < self.tolerance)


class Push(Task):
    """Push a cube until its center lies inside a 5 cm goal disc on the table."""

    name = "push"
    xml = "push.xml"
    instruction = "push the red cube into the green circle"
    max_steps = 150
    tolerance = 0.05

    def _sample_scene(self) -> None:
        cube = self._uniform([-0.12, -0.12, 0.0], [0.12, 0.12, 0.0])
        cube[2] = 0.025
        # Place the goal 10 to 18 cm away from the cube in a random direction.
        angle = float(self._uniform(-np.pi, np.pi))
        dist = float(self._uniform(0.10, 0.18))
        goal = cube[:2] + dist * np.array([np.cos(angle), np.sin(angle)])
        goal = np.clip(goal, -0.25, 0.25)
        self._set_free_body("cube", cube, yaw=float(self._uniform(-np.pi, np.pi)))
        self.model.site_pos[self.model.site("goal").id] = [goal[0], goal[1], 0.001]

    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        return {"object_pos": self.body_pos("cube"), "goal_pos": self.site_pos("goal")}

    def is_success(self) -> bool:
        delta = self.body_pos("cube")[:2] - self.site_pos("goal")[:2]
        return bool(np.linalg.norm(delta) < self.tolerance)


class PickPlace(Task):
    """Lift a cube and hold it within 3 cm of a goal point above the table."""

    name = "pick_place"
    xml = "pick_place.xml"
    instruction = "pick up the blue cube and move it to the green target"
    max_steps = 150
    tolerance = 0.03

    def _sample_scene(self) -> None:
        cube = self._uniform([-0.15, -0.15, 0.0], [0.15, 0.15, 0.0])
        cube[2] = 0.02
        goal = self._uniform([-0.15, -0.15, 0.08], [0.15, 0.15, 0.2])
        self._set_free_body("cube", cube, yaw=float(self._uniform(-np.pi, np.pi)))
        self.model.site_pos[self.model.site("goal").id] = goal

    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        return {"object_pos": self.body_pos("cube"), "goal_pos": self.site_pos("goal")}

    def is_success(self) -> bool:
        return bool(np.linalg.norm(self.body_pos("cube") - self.site_pos("goal")) < self.tolerance)


class Stack(Task):
    """Place the red cube on the blue cube and release it."""

    name = "stack"
    xml = "stack.xml"
    instruction = "stack the red cube on top of the blue cube"
    max_steps = 180
    xy_tolerance = 0.02
    z_tolerance = 0.008
    cube_size = 0.04

    def _sample_scene(self) -> None:
        top = self._uniform([-0.12, -0.12, 0.0], [0.12, 0.12, 0.0])
        # The base cube starts 8 to 14 cm from the top cube in a random direction.
        angle = float(self._uniform(-np.pi, np.pi))
        dist = float(self._uniform(0.08, 0.14))
        base = top + dist * np.array([np.cos(angle), np.sin(angle), 0.0])
        base[:2] = np.clip(base[:2], -0.22, 0.22)
        top[2] = base[2] = 0.02
        self._set_free_body("cube", top, yaw=float(self._uniform(-np.pi, np.pi)))
        self._set_free_body("base_cube", base, yaw=float(self._uniform(-np.pi, np.pi)))

    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        return {"object_pos": self.body_pos("cube"), "target_pos": self.body_pos("base_cube")}

    def is_success(self) -> bool:
        top = self.body_pos("cube")
        base = self.body_pos("base_cube")
        aligned = np.linalg.norm(top[:2] - base[:2]) < self.xy_tolerance
        on_top = abs(top[2] - base[2] - self.cube_size) < self.z_tolerance
        released = self.finger_opening > 0.6 * FINGER_OPEN
        return bool(aligned and on_top and released)


class Drawer(Task):
    """Pull the drawer at least 12 cm out of the cabinet."""

    name = "drawer"
    xml = "drawer.xml"
    instruction = "open the drawer"
    max_steps = 120
    open_threshold = 0.12

    def _sample_scene(self) -> None:
        cabinet = self.model.body("cabinet").id
        pos = self._uniform([0.2, -0.12, 0.0], [0.26, 0.12, 0.0])
        self.model.body_pos[cabinet] = pos

    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        return {
            "handle_pos": self.site_pos("handle"),
            "drawer_open": np.array([self.drawer_open]),
        }

    @property
    def drawer_open(self) -> float:
        return float(self.data.joint("drawer").qpos[0])

    def is_success(self) -> bool:
        return self.drawer_open > self.open_threshold


TASKS: dict[str, type[Task]] = {cls.name: cls for cls in (Reach, Push, PickPlace, Drawer, Stack)}

SUITES: dict[str, tuple[str, ...]] = {
    "core": ("reach", "push", "pick_place", "drawer", "stack"),
    "smoke": ("reach", "push"),
}


def make_task(name: str, randomization: Randomization | None = None) -> Task:
    """Builds a task by name."""
    try:
        cls = TASKS[name]
    except KeyError:
        raise ValueError(f"unknown task {name!r}; choose from {sorted(TASKS)}") from None
    return cls(randomization)


def resolve_tasks(suite: str | None = None, tasks: list[str] | None = None) -> list[str]:
    """Returns task names from an explicit list, or from a suite name."""
    if tasks:
        for t in tasks:
            if t not in TASKS:
                raise ValueError(f"unknown task {t!r}; choose from {sorted(TASKS)}")
        return list(tasks)
    name = suite or "core"
    if name not in SUITES:
        raise ValueError(f"unknown suite {name!r}; choose from {sorted(SUITES)}")
    return list(SUITES[name])
