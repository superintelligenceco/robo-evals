"""Renders docs/demo.gif: the scripted baseline solving every core task.

Each panel is one real, seeded episode from the harness. Run from the repo root::

    python scripts/render_demo.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import robo_evals  # noqa: F401  (configures the GL backend)
from robo_evals.policies import ScriptedPolicy
from robo_evals.seeding import episode_seed
from robo_evals.tasks import SUITES, make_task
from robo_evals.video import render_frame, try_make_renderer

WIDTH, HEIGHT = 240, 180
SEED = 0
HOLD = 12
OUT = Path(__file__).resolve().parents[1] / "docs" / "demo.gif"


def episode_frames(name: str) -> list[np.ndarray]:
    task = make_task(name)
    renderer = try_make_renderer(task.model, WIDTH, HEIGHT)
    if renderer is None:
        raise SystemExit("offscreen rendering is unavailable; set MUJOCO_GL=egl or osmesa")
    policy = ScriptedPolicy()
    seed = episode_seed(SEED, name, 0)
    obs = task.reset(seed)
    policy.reset(name, seed)
    frames = [render_frame(renderer, task.data)]
    for _ in range(task.max_steps):
        step = task.step(policy(obs))
        obs = step.observation
        frames.append(render_frame(renderer, task.data))
        if step.success:
            break
    renderer.close()
    outcome = f"{name}: {'success' if step.success else 'failure'}"
    captioned = [_caption(f, name) for f in frames]
    captioned += [_caption(frames[-1], outcome)] * HOLD
    return captioned


def _caption(frame: np.ndarray, text: str) -> np.ndarray:
    image = Image.fromarray(frame)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 16), fill=(20, 20, 20))
    draw.text((6, 3), text, fill=(240, 240, 240))
    return np.asarray(image)


def main() -> None:
    frames: list[np.ndarray] = []
    for name in SUITES["core"]:
        frames += episode_frames(name)
    images = [Image.fromarray(f).quantize(colors=96, dither=Image.Dither.NONE) for f in frames[::2]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        OUT, save_all=True, append_images=images[1:], duration=100, loop=0, optimize=True
    )
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KiB, {len(images)} frames)")


if __name__ == "__main__":
    main()
