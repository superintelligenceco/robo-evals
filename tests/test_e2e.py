"""End to end: the harness separates the scripted oracle from random actions."""

from __future__ import annotations

import pytest

from robo_evals import TASKS, evaluate, load_policy

EPISODES = 5


@pytest.fixture(scope="module")
def results() -> dict[str, dict[str, float]]:
    out = {}
    for name in ("scripted", "random"):
        r = evaluate(load_policy(name), suite="core", episodes=EPISODES, seed=0)
        out[name] = {t.task: t.success_rate for t in r.tasks}
    return out


@pytest.mark.parametrize("task", sorted(TASKS))
def test_oracle_beats_random_by_a_wide_margin(
    results: dict[str, dict[str, float]], task: str
) -> None:
    oracle = results["scripted"][task]
    rand = results["random"][task]
    assert oracle >= 0.8, f"scripted policy solved only {oracle:.0%} of {task}"
    assert oracle - rand >= 0.6


@pytest.mark.parametrize("task", sorted(TASKS))
def test_oracle_ci_excludes_random_ci(task: str) -> None:
    oracle = evaluate(load_policy("scripted"), tasks=[task], episodes=10, seed=1).tasks[0]
    rand = evaluate(load_policy("random"), tasks=[task], episodes=10, seed=1).tasks[0]
    assert oracle.ci[0] > rand.ci[1]
