"""Hot-path benchmarks for the evaluation loop.

Run with ``make bench``. ``scripts/bench_gate.py`` then checks the harness
overhead: the time of one ``Task.step`` against the raw MuJoCo physics it wraps,
measured in the same process on the same machine, so the gate holds on any CPU.
"""

from __future__ import annotations

from typing import Any

import mujoco
import numpy as np

import robo_evals  # noqa: F401  (configures the GL backend before mujoco loads)
from robo_evals import evaluate, load_policy
from robo_evals.env import SUBSTEPS
from robo_evals.seeding import episode_seed
from robo_evals.stats import wilson_interval
from robo_evals.tasks import make_task

ACTION = np.array([0.3, -0.2, 0.1, 0.0])


def test_bench_raw_physics_control_step(benchmark: Any) -> None:
    task = make_task("pick_place")
    task.reset(0)

    def physics() -> None:
        mujoco.mj_step(task.model, task.data, nstep=SUBSTEPS)

    benchmark.pedantic(physics, rounds=300, iterations=5, warmup_rounds=20)


def test_bench_task_step(benchmark: Any) -> None:
    task = make_task("pick_place")
    task.reset(0)

    def step() -> None:
        task.step(ACTION)

    benchmark.pedantic(step, rounds=300, iterations=5, warmup_rounds=20)


def test_bench_task_reset(benchmark: Any) -> None:
    task = make_task("stack")
    benchmark(task.reset, 123)


def test_bench_evaluate_scripted_smoke(benchmark: Any) -> None:
    policy = load_policy("scripted")
    result = benchmark.pedantic(
        lambda: evaluate(policy, suite="smoke", episodes=3, seed=0), rounds=3, iterations=1
    )
    assert result.overall["success_rate"] == 1.0


def test_bench_wilson_interval(benchmark: Any) -> None:
    benchmark(wilson_interval, 37, 50)


def test_bench_episode_seed(benchmark: Any) -> None:
    benchmark(episode_seed, 0, "pick_place", 17)
