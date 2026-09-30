from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import robo_evals.runner as runner
from robo_evals import evaluate, load_policy
from robo_evals.report import to_markdown
from robo_evals.video import write_video


def _frames(n: int = 4) -> list[np.ndarray]:
    return [np.full((24, 32, 3), 40 * i, dtype=np.uint8) for i in range(n)]


def test_write_gif(tmp_path: Path) -> None:
    path = write_video(_frames(), tmp_path / "a.gif")
    assert path.suffix == ".gif"
    assert path.stat().st_size > 0


def test_write_mp4_or_fallback(tmp_path: Path) -> None:
    path = write_video(_frames(), tmp_path / "a.mp4")
    assert path.exists()
    assert path.suffix in (".mp4", ".gif")


def test_write_video_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no frames"):
        write_video([], tmp_path / "a.gif")
    with pytest.raises(ValueError, match="unsupported"):
        write_video(_frames(), tmp_path / "a.avi")


def test_videos_are_recorded(tmp_path: Path, can_render: bool) -> None:
    if not can_render:
        pytest.skip("offscreen rendering is unavailable here")
    r = evaluate(
        load_policy("scripted"),
        tasks=["reach"],
        episodes=2,
        video="first",
        video_dir=tmp_path,
        video_size=(64, 48),
    )
    assert r.video_available is True
    first, second = r.tasks[0].episodes
    assert first.video is not None
    assert Path(first.video).exists()
    assert second.video is None


def test_failures_mode_keeps_only_failures(tmp_path: Path, can_render: bool) -> None:
    if not can_render:
        pytest.skip("offscreen rendering is unavailable here")
    r = evaluate(
        load_policy("scripted"),
        tasks=["reach"],
        episodes=2,
        video="failures",
        video_dir=tmp_path,
        video_size=(64, 48),
    )
    assert all(e.video is None for e in r.tasks[0].episodes)


def test_image_observations(can_render: bool) -> None:
    if not can_render:
        pytest.skip("offscreen rendering is unavailable here")
    shapes = []

    def policy(obs: dict[str, np.ndarray]) -> list[float]:
        shapes.append(obs["image"].shape)
        return [0.0, 0.0, 0.0, -1.0]

    evaluate(policy, tasks=["reach"], episodes=1, max_steps=2, image_obs=True, image_size=(40, 30))
    assert shapes == [(30, 40, 3)] * 2


def test_scoring_continues_without_renderer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "try_make_renderer", lambda *a, **k: None)
    r = evaluate(
        load_policy("scripted"), tasks=["reach"], episodes=2, video="all", video_dir=tmp_path
    )
    assert r.video_available is False
    assert r.tasks[0].successes == 2
    assert all(e.video is None for e in r.tasks[0].episodes)
    assert "offscreen rendering was unavailable" in to_markdown(r)
    with pytest.raises(RuntimeError, match="image observations"):
        evaluate(load_policy("zero"), tasks=["reach"], episodes=1, image_obs=True)

