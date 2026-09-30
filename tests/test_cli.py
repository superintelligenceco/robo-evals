from __future__ import annotations

import json
from pathlib import Path

import pytest

from robo_evals import __version__
from robo_evals.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for word in ("reach", "push", "pick_place", "drawer", "stack", "core", "wide"):
        assert word in out


def test_run_and_compare(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for policy in ("random", "scripted"):
        code = main(
            [
                "run",
                "--policy",
                policy,
                "--tasks",
                "reach",
                "--episodes",
                "2",
                "--out",
                str(tmp_path),
                "-q",
            ]
        )
        assert code == 0
    report = json.loads((tmp_path / "scripted" / "report.json").read_text())
    assert report["tasks"][0]["successes"] == 2
    assert (tmp_path / "random" / "report.md").exists()
    capsys.readouterr()
    table_path = tmp_path / "table.md"
    assert (
        main(
            [
                "compare",
                str(tmp_path / "random" / "report.json"),
                str(tmp_path / "scripted" / "report.json"),
                "--out",
                str(table_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "`random`" in out
    assert "`scripted`" in out
    assert table_path.read_text() == out


def test_run_example_file_policy(tmp_path: Path) -> None:
    spec = f"{ROOT / 'examples' / 'my_policy.py'}:ReachPolicy"
    code = main(
        [
            "run",
            "--policy",
            spec,
            "--tasks",
            "reach",
            "--episodes",
            "3",
            "--name",
            "mine",
            "--out",
            str(tmp_path),
            "-q",
        ]
    )
    assert code == 0
    report = json.loads((tmp_path / "mine" / "report.json").read_text())
    assert report["overall"]["successes"] == 3


def test_errors_exit_with_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--policy", "nope"]) == 2
    assert "error:" in capsys.readouterr().err
