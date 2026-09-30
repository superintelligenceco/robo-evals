from __future__ import annotations

import json
from pathlib import Path

import pytest

from robo_evals import evaluate, load_policy
from robo_evals.report import compare_markdown, load_report, to_markdown, write_reports
from robo_evals.runner import EpisodeResult, EvalResult, TaskResult


def _fake_result() -> EvalResult:
    eps = [EpisodeResult("reach", i, i, i < 3, 10, 5 if i < 3 else None) for i in range(4)]
    return EvalResult(
        policy="fake",
        config={
            "tasks": ["reach"],
            "episodes": 4,
            "seed": 0,
            "randomization": {},
            "confidence": 0.95,
        },
        tasks=[TaskResult("reach", "move", eps)],
        environment={"robo_evals": "0", "mujoco": "0", "python": "3", "machine": "x"},
    )


def test_task_result_aggregates() -> None:
    t = _fake_result().tasks[0]
    assert (t.n, t.successes, t.success_rate) == (4, 3, 0.75)
    assert t.mean_steps_to_success == 5.0
    lo, hi = t.ci
    assert lo < 0.75 < hi


def test_same_seed_gives_identical_reports() -> None:
    kwargs = {"tasks": ["reach", "push"], "episodes": 3, "seed": 11}
    a = evaluate(load_policy("random"), **kwargs).to_dict()
    b = evaluate(load_policy("random"), **kwargs).to_dict()
    for d in (a, b):
        d.pop("wall_time_s")
    assert a == b


def test_episode_seeds_do_not_depend_on_task_order() -> None:
    a = evaluate(load_policy("zero"), tasks=["reach", "push"], episodes=2, seed=3)
    b = evaluate(load_policy("zero"), tasks=["push", "reach"], episodes=2, seed=3)
    seeds_a = {t.task: [e.seed for e in t.episodes] for t in a.tasks}
    seeds_b = {t.task: [e.seed for e in t.episodes] for t in b.tasks}
    assert seeds_a == seeds_b


def test_max_steps_override_and_progress() -> None:
    seen: list[EpisodeResult] = []
    r = evaluate(
        load_policy("zero"), tasks=["reach"], episodes=2, max_steps=5, progress=seen.append
    )
    assert [e.steps for e in r.tasks[0].episodes] == [5, 5]
    assert len(seen) == 2


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"episodes": 0}, "episodes"),
        ({"video": "some"}, "video must be"),
        ({"video": "first"}, "video_dir"),
        ({"video_format": "avi"}, "video_format"),
    ],
)
def test_argument_validation(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        evaluate(load_policy("zero"), tasks=["reach"], **kwargs)  # type: ignore[arg-type]


def test_reports_round_trip(tmp_path: Path) -> None:
    result = evaluate(load_policy("scripted"), tasks=["reach"], episodes=2, seed=0)
    json_path, md_path = write_reports(result, tmp_path)
    data = load_report(json_path)
    assert data["schema"] == "robo-evals/report/1"
    assert data["overall"]["episodes"] == 2
    assert data["tasks"][0]["episode_results"][0]["seed"] == result.tasks[0].episodes[0].seed
    md = md_path.read_text()
    assert "| reach |" in md
    assert "95% Wilson CI" in md
    assert to_markdown(data) == md


def test_markdown_formatting() -> None:
    md = to_markdown(_fake_result())
    assert "| reach | 75.0% [30.1, 95.4] (3/4) | 5.0 |" in md
    assert "| **overall** | 75.0% [30.1, 95.4] (3/4) | |" in md


def test_compare_table(tmp_path: Path) -> None:
    a = _fake_result().to_dict()
    b = json.loads(json.dumps(a))
    b["policy"] = "other"
    table = compare_markdown([a, b])
    assert "| Task | `fake` | `other` |" in table
    assert table.count("75.0%") == 4
    with pytest.raises(ValueError, match="at least one"):
        compare_markdown([])


def test_load_report_rejects_other_json(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{}")
    with pytest.raises(ValueError, match="not a robo-evals report"):
        load_report(p)
