"""Runs policies on tasks and aggregates the results."""

from __future__ import annotations

import logging
import platform
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from robo_evals import __version__
from robo_evals.policy import Policy, reset_policy
from robo_evals.randomization import Randomization
from robo_evals.seeding import episode_seed
from robo_evals.stats import wilson_interval
from robo_evals.tasks import make_task, resolve_tasks
from robo_evals.video import VIDEO_FORMATS, render_frame, try_make_renderer, write_video

logger = logging.getLogger(__name__)

VIDEO_MODES = ("none", "first", "failures", "all")


@dataclass
class EpisodeResult:
    task: str
    episode: int
    seed: int
    success: bool
    steps: int
    steps_to_success: int | None
    video: str | None = None


@dataclass
class TaskResult:
    task: str
    instruction: str
    episodes: list[EpisodeResult]
    confidence: float = 0.95

    @property
    def n(self) -> int:
        return len(self.episodes)

    @property
    def successes(self) -> int:
        return sum(e.success for e in self.episodes)

    @property
    def success_rate(self) -> float:
        return self.successes / self.n if self.n else 0.0

    @property
    def ci(self) -> tuple[float, float]:
        return wilson_interval(self.successes, self.n, self.confidence)

    @property
    def mean_steps_to_success(self) -> float | None:
        steps = [e.steps_to_success for e in self.episodes if e.steps_to_success is not None]
        return float(np.mean(steps)) if steps else None

    def summary(self) -> dict[str, Any]:
        low, high = self.ci
        return {
            "task": self.task,
            "instruction": self.instruction,
            "episodes": self.n,
            "successes": self.successes,
            "success_rate": self.success_rate,
            "ci_low": low,
            "ci_high": high,
            "mean_steps_to_success": self.mean_steps_to_success,
        }


@dataclass
class EvalResult:
    policy: str
    config: dict[str, Any]
    tasks: list[TaskResult]
    environment: dict[str, Any] = field(default_factory=dict)
    video_available: bool | None = None
    wall_time_s: float = 0.0

    @property
    def overall(self) -> dict[str, Any]:
        """Pooled successes over every episode, plus the unweighted mean of task rates."""
        n = sum(t.n for t in self.tasks)
        k = sum(t.successes for t in self.tasks)
        conf = float(self.config.get("confidence", 0.95))
        low, high = wilson_interval(k, n, conf)
        rates = [t.success_rate for t in self.tasks]
        return {
            "episodes": n,
            "successes": k,
            "success_rate": k / n if n else 0.0,
            "ci_low": low,
            "ci_high": high,
            "mean_task_success_rate": float(np.mean(rates)) if rates else 0.0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "robo-evals/report/1",
            "policy": self.policy,
            "config": self.config,
            "environment": self.environment,
            "video_available": self.video_available,
            "wall_time_s": self.wall_time_s,
            "overall": self.overall,
            "tasks": [
                {**t.summary(), "episode_results": [asdict(e) for e in t.episodes]}
                for t in self.tasks
            ],
        }


def environment_info() -> dict[str, Any]:
    return {
        "robo_evals": __version__,
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def _want_video(mode: str, episode: int) -> bool:
    """Whether to record frames. ``failures`` records every episode and keeps only failures."""
    if mode == "first":
        return episode == 0
    return mode in ("all", "failures")


def evaluate(
    policy: Policy,
    *,
    suite: str | None = "core",
    tasks: list[str] | None = None,
    episodes: int = 10,
    seed: int = 0,
    randomization: Randomization | None = None,
    max_steps: int | None = None,
    policy_name: str = "policy",
    video: str = "none",
    video_dir: str | Path | None = None,
    video_format: str = "gif",
    video_size: tuple[int, int] = (320, 240),
    image_obs: bool = False,
    image_size: tuple[int, int] = (128, 128),
    confidence: float = 0.95,
    progress: Callable[[EpisodeResult], None] | None = None,
) -> EvalResult:
    """Evaluates ``policy`` on each task for ``episodes`` seeded episodes.

    Args:
        policy: A callable ``obs -> action``, optionally with ``reset(task, seed)``.
        suite: Named task suite, used when ``tasks`` is empty.
        tasks: Explicit task names. Overrides ``suite``.
        episodes: Episodes per task.
        seed: Base seed. Episode seeds derive from it, the task name, and the index.
        randomization: Domain randomization settings. Defaults to ``Randomization()``.
        max_steps: Overrides each task's step limit.
        video: ``none``, ``first`` (episode 0 of each task), ``failures``, or ``all``.
        video_dir: Where to write videos. Required when ``video`` is not ``none``.
        video_format: ``gif`` or ``mp4``.
        image_obs: Adds a rendered ``image`` (H x W x 3 uint8) to every observation.
            Raises ``RuntimeError`` if rendering is unavailable.
        confidence: Confidence level of the Wilson intervals.
        progress: Called after every episode.
    """
    if episodes < 1:
        raise ValueError("episodes must be at least 1")
    if video not in VIDEO_MODES:
        raise ValueError(f"video must be one of {VIDEO_MODES}, got {video!r}")
    if video_format not in VIDEO_FORMATS:
        raise ValueError(f"video_format must be one of {VIDEO_FORMATS}, got {video_format!r}")
    if video != "none" and video_dir is None:
        raise ValueError("video_dir is required when video is enabled")
    randomization = randomization if randomization is not None else Randomization()
    task_names = resolve_tasks(suite, tasks)
    config = {
        "suite": None if tasks else (suite or "core"),
        "tasks": task_names,
        "episodes": episodes,
        "seed": seed,
        "randomization": randomization.to_dict(),
        "max_steps": max_steps,
        "image_obs": image_obs,
        "confidence": confidence,
    }
    start = time.perf_counter()
    results: list[TaskResult] = []
    video_available: bool | None = None
    for name in task_names:
        task = make_task(name, randomization)
        renderer = None
        if video != "none" and video_available is not False:
            renderer = try_make_renderer(task.model, *video_size)
            video_available = renderer is not None
        image_renderer = None
        if image_obs:
            image_renderer = try_make_renderer(task.model, *image_size)
            if image_renderer is None:
                raise RuntimeError("image observations need offscreen rendering; see logs")
        limit = max_steps if max_steps is not None else task.max_steps
        episode_results = []
        for i in range(episodes):
            ep_seed = episode_seed(seed, name, i)
            record = renderer is not None and _want_video(video, i)
            frames: list[np.ndarray] = []
            obs = task.reset(ep_seed)
            reset_policy(policy, name, ep_seed)
            if image_renderer is not None:
                obs["image"] = render_frame(image_renderer, task.data)
            if record:
                frames.append(render_frame(renderer, task.data))
            success = False
            steps_to_success = None
            steps = 0
            for steps in range(1, limit + 1):
                step = task.step(policy(obs))
                obs = step.observation
                if image_renderer is not None:
                    obs["image"] = render_frame(image_renderer, task.data)
                if record:
                    frames.append(render_frame(renderer, task.data))
                if step.success:
                    success = True
                    steps_to_success = steps
                    break
            if record and frames:
                # Hold the final frame so the outcome is visible when the GIF loops.
                frames.extend([frames[-1]] * 10)
            video_path = None
            keep = record and (video != "failures" or not success)
            if keep and video_dir is not None:
                path = Path(video_dir) / f"{name}_ep{i:03d}.{video_format}"
                video_path = str(write_video(frames, path))
            result = EpisodeResult(name, i, ep_seed, success, steps, steps_to_success, video_path)
            episode_results.append(result)
            if progress is not None:
                progress(result)
        for r in (renderer, image_renderer):
            if r is not None:
                r.close()
        results.append(TaskResult(name, task.instruction, episode_results, confidence))
    return EvalResult(
        policy=policy_name,
        config=config,
        tasks=results,
        environment=environment_info(),
        video_available=video_available,
        wall_time_s=time.perf_counter() - start,
    )
