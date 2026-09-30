"""JSON and Markdown reports."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from robo_evals.runner import EvalResult


def to_json(result: EvalResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=False) + "\n"


def load_report(path: str | Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "robo-evals/report/1":
        raise ValueError(f"{path} is not a robo-evals report")
    return data


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def format_rate(row: Mapping[str, Any]) -> str:
    """Formats a success rate as ``95.0% [83.5, 98.6]`` (k/n)."""
    return (
        f"{_pct(row['success_rate'])} "
        f"[{100 * row['ci_low']:.1f}, {100 * row['ci_high']:.1f}] "
        f"({row['successes']}/{row['episodes']})"
    )


def to_markdown(report: EvalResult | Mapping[str, Any]) -> str:
    """Renders one report as Markdown."""
    data = report.to_dict() if isinstance(report, EvalResult) else report
    cfg = data["config"]
    conf = round(100 * cfg["confidence"])
    lines = [
        f"# robo-evals report: `{data['policy']}`",
        "",
        f"- Tasks: {', '.join(cfg['tasks'])}",
        f"- Episodes per task: {cfg['episodes']}, base seed: {cfg['seed']}",
        f"- Randomization: `{json.dumps(cfg['randomization'])}`",
        f"- Environment: robo-evals {data['environment'].get('robo_evals')}, "
        f"MuJoCo {data['environment'].get('mujoco')}, "
        f"Python {data['environment'].get('python')} on {data['environment'].get('machine')}",
        "",
        f"| Task | Success rate [{conf}% Wilson CI] (k/n) | Mean steps to success |",
        "| --- | --- | --- |",
    ]
    for row in data["tasks"]:
        steps = row["mean_steps_to_success"]
        steps_s = f"{steps:.1f}" if steps is not None else "n/a"
        lines.append(f"| {row['task']} | {format_rate(row)} | {steps_s} |")
    lines.append(f"| **overall** | {format_rate(data['overall'])} | |")
    lines.append("")
    videos = [
        (row["task"], ep["episode"], ep["video"], ep["success"])
        for row in data["tasks"]
        for ep in row["episode_results"]
        if ep.get("video")
    ]
    if videos:
        lines += ["## Videos", ""]
        for task, ep, path, ok in videos:
            lines.append(f"- {task} episode {ep} ({'success' if ok else 'failure'}): `{path}`")
        lines.append("")
    elif data.get("video_available") is False:
        lines += ["Videos were requested but offscreen rendering was unavailable.", ""]
    return "\n".join(lines)


def compare_markdown(reports: Sequence[Mapping[str, Any]]) -> str:
    """Renders a side-by-side success-rate table for several reports."""
    if not reports:
        raise ValueError("need at least one report")
    names = [r["policy"] for r in reports]
    tasks: list[str] = []
    for r in reports:
        for row in r["tasks"]:
            if row["task"] not in tasks:
                tasks.append(row["task"])
    by_policy = [{row["task"]: row for row in r["tasks"]} for r in reports]
    lines = [
        "| Task | " + " | ".join(f"`{n}`" for n in names) + " |",
        "| --- |" + " --- |" * len(names),
    ]
    for task in tasks:
        cells = [format_rate(p[task]) if task in p else "n/a" for p in by_policy]
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    lines.append(
        "| **overall** | " + " | ".join(f"**{format_rate(r['overall'])}**" for r in reports) + " |"
    )
    return "\n".join(lines) + "\n"


def write_reports(result: EvalResult, out_dir: str | Path) -> tuple[Path, Path]:
    """Writes ``report.json`` and ``report.md`` into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "report.json"
    md_path = out / "report.md"
    json_path.write_text(to_json(result), encoding="utf-8")
    md_path.write_text(to_markdown(result), encoding="utf-8")
    return json_path, md_path
