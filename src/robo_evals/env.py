"""MuJoCo environment core shared by every task."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, ClassVar

import mujoco
import numpy as np
from numpy.typing import ArrayLike, NDArray

from robo_evals.randomization import Randomization

Observation = dict[str, Any]
"""An observation: named ``numpy`` arrays plus the ``instruction`` string."""

ACTION_DIM = 4
"""Actions are ``[dx, dy, dz, grip]``, each clipped to ``[-1, 1]``."""

MAX_DELTA = 0.03
"""Metres the end-effector target moves per step at full action magnitude."""

SUBSTEPS = 25
"""Physics steps per control step (0.002 s timestep, so 20 Hz control)."""

FINGER_OPEN = 0.045
WORKSPACE_LOW = np.array([-0.35, -0.35, 0.005])
WORKSPACE_HIGH = np.array([0.35, 0.35, 0.45])
HOME = np.array([0.0, -0.1, 0.2])


@dataclass
class StepResult:
    observation: Observation
    success: bool
    info: dict[str, Any] = field(default_factory=dict)


def _asset_path(name: str) -> str:
    return str(resources.files("robo_evals").joinpath("assets", name))


class Task(abc.ABC):
    """A seeded manipulation task on the shared floating-gripper scene.

    Subclasses set ``name``, ``xml``, ``instruction`` and ``max_steps`` and
    implement ``_sample_scene``, ``_task_obs`` and ``is_success``.
    """

    name: ClassVar[str]
    xml: ClassVar[str]
    instruction: ClassVar[str]
    max_steps: ClassVar[int] = 150

    def __init__(self, randomization: Randomization | None = None) -> None:
        self.randomization = randomization if randomization is not None else Randomization()
        self.model = mujoco.MjModel.from_xml_path(_asset_path(self.xml))
        self.data = mujoco.MjData(self.model)
        self._defaults = {
            "geom_friction": self.model.geom_friction.copy(),
            "light_pos": self.model.light_pos.copy(),
            "light_dir": self.model.light_dir.copy(),
            "light_diffuse": self.model.light_diffuse.copy(),
            "headlight_ambient": self.model.vis.headlight.ambient.copy(),
            "site_pos": self.model.site_pos.copy(),
            "body_pos": self.model.body_pos.copy(),
        }
        self._grip_site = self.model.site("grip").id
        self._ee_qpos = np.array([self.model.joint(f"ee_{a}").qposadr[0] for a in "xyz"])
        self._finger_qpos = np.array([self.model.joint(f"finger_{s}").qposadr[0] for s in "lr"])
        self.rng = np.random.default_rng(0)
        self.steps = 0
        self.seed: int | None = None

    # -- public API -----------------------------------------------------------------

    def reset(self, seed: int) -> Observation:
        """Resets the scene deterministically from ``seed`` and returns the first observation."""
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        m = self.model
        m.geom_friction[:] = self._defaults["geom_friction"]
        m.light_pos[:] = self._defaults["light_pos"]
        m.light_dir[:] = self._defaults["light_dir"]
        m.light_diffuse[:] = self._defaults["light_diffuse"]
        m.vis.headlight.ambient[:] = self._defaults["headlight_ambient"]
        m.site_pos[:] = self._defaults["site_pos"]
        m.body_pos[:] = self._defaults["body_pos"]
        mujoco.mj_resetData(m, self.data)

        self._randomize_physics()
        self._randomize_lighting()
        self._sample_scene()

        home = HOME + self._uniform(np.array([-0.03, -0.03, -0.02]), np.array([0.03, 0.03, 0.02]))
        self.data.qpos[self._ee_qpos] = home
        self.data.qpos[self._finger_qpos] = FINGER_OPEN
        self.data.ctrl[:3] = home
        self.data.ctrl[3:5] = FINGER_OPEN
        mujoco.mj_forward(m, self.data)
        # Let objects settle before the policy acts.
        mujoco.mj_step(m, self.data, nstep=100)
        self.steps = 0
        return self.observation()

    def step(self, action: ArrayLike) -> StepResult:
        """Applies one action and advances the simulation by one control step."""
        a = np.asarray(action, dtype=np.float64).reshape(-1)
        if a.shape != (ACTION_DIM,):
            raise ValueError(f"action must have {ACTION_DIM} elements, got shape {a.shape}")
        if not np.all(np.isfinite(a)):
            raise ValueError("action contains NaN or inf")
        a = np.clip(a, -1.0, 1.0)
        target = np.clip(self.ee_pos + a[:3] * MAX_DELTA, WORKSPACE_LOW, WORKSPACE_HIGH)
        self.data.ctrl[:3] = target
        self.data.ctrl[3:5] = FINGER_OPEN * (1.0 - a[3]) / 2.0
        mujoco.mj_step(self.model, self.data, nstep=SUBSTEPS)
        self.steps += 1
        return StepResult(self.observation(), self.is_success(), {"step": self.steps})

    def observation(self) -> Observation:
        obs: Observation = {
            "ee_pos": self.ee_pos.copy(),
            "gripper": np.array([self.finger_opening / FINGER_OPEN]),
        }
        obs.update(self._task_obs())
        obs["state"] = np.concatenate(
            [np.asarray(v, dtype=np.float64).reshape(-1) for v in obs.values()]
        )
        obs["instruction"] = self.instruction
        return obs

    @property
    def ee_pos(self) -> NDArray[np.float64]:
        return np.asarray(self.data.site_xpos[self._grip_site])

    @property
    def finger_opening(self) -> float:
        return float(np.mean(self.data.qpos[self._finger_qpos]))

    def body_pos(self, name: str) -> NDArray[np.float64]:
        return np.asarray(self.data.body(name).xpos).copy()

    def site_pos(self, name: str) -> NDArray[np.float64]:
        return np.asarray(self.data.site(name).xpos).copy()

    @abc.abstractmethod
    def is_success(self) -> bool:
        """Evaluates the task's success predicate on the current state."""

    # -- helpers for subclasses -----------------------------------------------------

    @abc.abstractmethod
    def _sample_scene(self) -> None:
        """Places objects and goals using ``self.rng``."""

    @abc.abstractmethod
    def _task_obs(self) -> dict[str, NDArray[np.float64]]:
        """Returns the task-specific observation entries."""

    def _uniform(self, low: ArrayLike, high: ArrayLike) -> NDArray[np.float64]:
        """Draws uniformly from a range shrunk around its center by ``object_pose``."""
        low_a = np.asarray(low, dtype=np.float64)
        high_a = np.asarray(high, dtype=np.float64)
        center = (low_a + high_a) / 2.0
        half = (high_a - low_a) / 2.0 * self.randomization.object_pose
        return np.asarray(self.rng.uniform(center - half, center + half))

    def _set_free_body(self, joint: str, pos: ArrayLike, yaw: float = 0.0) -> None:
        adr = self.model.joint(joint).qposadr[0]
        self.data.qpos[adr : adr + 3] = pos
        self.data.qpos[adr + 3 : adr + 7] = [np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)]

    def _randomize_physics(self) -> None:
        low, high = self.randomization.friction
        scale = self.rng.uniform(low, high)
        self.model.geom_friction[:, 0] = self._defaults["geom_friction"][:, 0] * scale

    def _randomize_lighting(self) -> None:
        # Draw even when disabled so enabling lighting never shifts other draws.
        jitter = self.rng.uniform(-0.3, 0.3, size=(self.model.nlight, 3))
        gain = self.rng.uniform(0.6, 1.3, size=(self.model.nlight, 1))
        ambient = self.rng.uniform(0.2, 0.5)
        if not self.randomization.lighting:
            return
        self.model.light_pos[:] = self._defaults["light_pos"] + jitter
        self.model.light_diffuse[:] = np.clip(self._defaults["light_diffuse"] * gain, 0.0, 1.0)
        self.model.vis.headlight.ambient[:] = ambient
