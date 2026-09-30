"""Task construction, determinism, and success predicates."""

from __future__ import annotations

import numpy as np
import pytest

from robo_evals.env import ACTION_DIM, FINGER_OPEN, Task
from robo_evals.randomization import Randomization, get_preset
from robo_evals.tasks import SUITES, TASKS, make_task, resolve_tasks

ALL_TASKS = sorted(TASKS)


def _rollout(task: Task, seed: int, actions: np.ndarray) -> np.ndarray:
    obs = task.reset(seed)
    states = [obs["state"]]
    for a in actions:
        states.append(task.step(a).observation["state"])
    return np.stack(states)


@pytest.mark.parametrize("name", ALL_TASKS)
def test_observation_contract(name: str) -> None:
    task = make_task(name)
    obs = task.reset(0)
    assert obs["instruction"] == task.instruction
    assert obs["ee_pos"].shape == (3,)
    assert obs["gripper"].shape == (1,)
    assert obs["state"].ndim == 1
    assert np.all(np.isfinite(obs["state"]))
    assert not task.is_success(), "a freshly reset scene must not already be solved"


@pytest.mark.parametrize("name", ALL_TASKS)
def test_same_seed_same_trajectory(name: str) -> None:
    actions = np.random.default_rng(1).uniform(-1, 1, size=(15, ACTION_DIM))
    a = _rollout(make_task(name), 42, actions)
    b = _rollout(make_task(name), 42, actions)
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", ALL_TASKS)
def test_reset_is_repeatable_on_one_instance(name: str) -> None:
    task = make_task(name)
    actions = np.random.default_rng(2).uniform(-1, 1, size=(10, ACTION_DIM))
    first = _rollout(task, 7, actions)
    _rollout(task, 8, actions)
    np.testing.assert_array_equal(first, _rollout(task, 7, actions))


@pytest.mark.parametrize("name", ALL_TASKS)
def test_different_seeds_change_the_scene(name: str) -> None:
    task = make_task(name)
    s1 = task.reset(1)["state"]
    s2 = task.reset(2)["state"]
    assert not np.allclose(s1, s2)


def test_no_pose_randomization_centers_the_scene() -> None:
    task = make_task("reach", Randomization(object_pose=0.0, friction=(1.0, 1.0), lighting=False))
    g1 = task.reset(1)["goal_pos"]
    g2 = task.reset(2)["goal_pos"]
    np.testing.assert_allclose(g1, g2)
    np.testing.assert_allclose(g1, [0.0, 0.0, 0.175])


def test_friction_randomization_is_seeded_and_bounded() -> None:
    task = make_task("push", Randomization(friction=(0.5, 1.5)))
    base = task._defaults["geom_friction"][:, 0]
    task.reset(3)
    f3 = task.model.geom_friction[:, 0].copy()
    task.reset(4)
    f4 = task.model.geom_friction[:, 0].copy()
    task.reset(3)
    np.testing.assert_array_equal(task.model.geom_friction[:, 0], f3)
    assert not np.allclose(f3, f4)
    ratio = f3 / base
    assert np.all((ratio >= 0.5) & (ratio <= 1.5))


def test_lighting_toggle_does_not_change_physics() -> None:
    on = make_task("push", Randomization(lighting=True))
    off = make_task("push", Randomization(lighting=False))
    np.testing.assert_array_equal(on.reset(5)["state"], off.reset(5)["state"])
    assert not np.allclose(on.model.light_diffuse, off.model.light_diffuse)


def test_action_validation() -> None:
    task = make_task("reach")
    task.reset(0)
    with pytest.raises(ValueError, match="4 elements"):
        task.step([0.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="NaN"):
        task.step([np.nan, 0.0, 0.0, 0.0])
    # Out-of-range actions are clipped, not rejected.
    task.step([10.0, -10.0, 0.0, 5.0])


def test_reach_predicate() -> None:
    task = make_task("reach")
    task.reset(0)
    goal = task.site_pos("goal")
    task.data.qpos[task._ee_qpos] = goal
    task.data.ctrl[:3] = goal
    import mujoco

    mujoco.mj_forward(task.model, task.data)
    assert task.is_success()
    task.data.qpos[task._ee_qpos] = goal + np.array([0.05, 0.0, 0.0])
    mujoco.mj_forward(task.model, task.data)
    assert not task.is_success()


def _place(task: Task, joint: str, pos: np.ndarray) -> None:
    import mujoco

    task._set_free_body(joint, pos)
    mujoco.mj_forward(task.model, task.data)


def test_push_predicate() -> None:
    task = make_task("push")
    task.reset(0)
    goal = task.site_pos("goal")
    _place(task, "cube", np.array([goal[0] + 0.03, goal[1], 0.025]))
    assert task.is_success()
    _place(task, "cube", np.array([goal[0] + 0.07, goal[1], 0.025]))
    assert not task.is_success()


def test_pick_place_predicate_needs_height() -> None:
    task = make_task("pick_place")
    task.reset(0)
    goal = task.site_pos("goal")
    _place(task, "cube", goal)
    assert task.is_success()
    _place(task, "cube", np.array([goal[0], goal[1], 0.02]))
    assert not task.is_success()


def test_stack_predicate() -> None:
    task = make_task("stack")
    task.reset(0)
    base = task.body_pos("base_cube")
    _place(task, "cube", base + np.array([0.0, 0.0, 0.04]))
    assert task.finger_opening > 0.6 * FINGER_OPEN
    assert task.is_success()
    _place(task, "cube", base + np.array([0.03, 0.0, 0.04]))
    assert not task.is_success(), "misaligned"
    _place(task, "cube", base + np.array([0.0, 0.0, 0.08]))
    assert not task.is_success(), "floating above"


def test_drawer_predicate() -> None:
    import mujoco

    task = make_task("drawer")
    task.reset(0)
    adr = task.model.joint("drawer").qposadr[0]
    task.data.qpos[adr] = 0.05
    mujoco.mj_forward(task.model, task.data)
    assert not task.is_success()
    task.data.qpos[adr] = 0.15
    mujoco.mj_forward(task.model, task.data)
    assert task.is_success()


def test_suites_and_resolution() -> None:
    assert set(SUITES["core"]) == set(TASKS)
    assert resolve_tasks("smoke") == list(SUITES["smoke"])
    assert resolve_tasks(None, ["drawer"]) == ["drawer"]
    with pytest.raises(ValueError, match="unknown suite"):
        resolve_tasks("nope")
    with pytest.raises(ValueError, match="unknown task"):
        resolve_tasks(None, ["nope"])
    with pytest.raises(ValueError, match="unknown task"):
        make_task("nope")


def test_randomization_validation() -> None:
    with pytest.raises(ValueError, match="object_pose"):
        Randomization(object_pose=1.5)
    with pytest.raises(ValueError, match="friction"):
        Randomization(friction=(1.2, 0.8))
    with pytest.raises(ValueError, match="unknown randomization preset"):
        get_preset("extreme")
    assert get_preset("none").lighting is False
