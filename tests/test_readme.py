"""Runs the README quickstart and Python API example, so the docs can't drift from the code."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from robo_evals.cli import main

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _section(title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## )", README, re.S | re.M)
    assert match, f"README has no '## {title}' section"
    return match.group(1)


def _blocks(text: str, lang: str) -> list[str]:
    return re.findall(rf"```{lang}\n(.*?)```", text, re.S)


def _quickstart_commands() -> list[list[str]]:
    commands = []
    for block in _blocks(_section("Quickstart"), "sh"):
        for line in block.splitlines():
            line = line.split("#", 1)[0].strip()
            if line.startswith("robo-evals ") and "path/to/" not in line:
                commands.append(shlex.split(line)[1:])
    return commands


def test_readme_has_a_runnable_quickstart() -> None:
    assert _quickstart_commands(), "no runnable robo-evals command in the Quickstart"


@pytest.mark.parametrize("argv", _quickstart_commands(), ids=lambda a: " ".join(a))
def test_quickstart_command_runs(
    argv: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(argv) == 0
    reports = list(tmp_path.glob("results/*/report.json"))
    assert reports, "the quickstart command wrote no report"
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["overall"]["success_rate"] == 1.0


def test_readme_python_api_example_runs(tmp_path: Path) -> None:
    (code,) = _blocks(_section("Python API"), "python")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), env.get("PYTHONPATH", "")])
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "results" / "scripted" / "report.json").is_file()
    assert "success_rate" in proc.stdout


def test_readme_install_line_names_the_pypi_package() -> None:
    assert re.search(r"pip install \"?robo-evals", _section("Install"))
