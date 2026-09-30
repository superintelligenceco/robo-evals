"""Offscreen rendering and episode video writing.

Rendering needs an OpenGL backend. On headless Linux, set ``MUJOCO_GL=egl``
(GPU or Mesa) or ``MUJOCO_GL=osmesa`` (pure software) before running. When no
backend works, ``try_make_renderer`` returns ``None`` and evaluation continues
without video.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

VIDEO_FORMATS = ("gif", "mp4")


def configure_gl_backend() -> None:
    """Picks a headless GL backend on Linux and imports ``mujoco`` safely.

    This must run before ``mujoco`` is first imported, because MuJoCo reads
    ``MUJOCO_GL`` at import time. If the chosen backend is broken (for example
    ``MUJOCO_GL=osmesa`` without the OSMesa library), importing ``mujoco``
    raises. In that case rendering is disabled so that physics and scoring
    still work and videos are skipped.
    """
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ.setdefault("MUJOCO_GL", "egl")
        if os.environ.get("MUJOCO_GL") == "egl":
            os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    if "mujoco" in sys.modules:
        return
    try:
        import mujoco
    except ImportError:
        raise
    except Exception as exc:  # A broken GL backend fails with many exception types.
        logger.warning(
            "MUJOCO_GL=%s failed to load (%s: %s); rendering is disabled.",
            os.environ.get("MUJOCO_GL"),
            type(exc).__name__,
            exc,
        )
        for name in list(sys.modules):
            if name.split(".")[0] in ("mujoco", "OpenGL"):
                del sys.modules[name]
        os.environ["MUJOCO_GL"] = "disable"
        os.environ.pop("PYOPENGL_PLATFORM", None)
        import mujoco  # noqa: F401


def try_make_renderer(model: Any, width: int, height: int) -> Any | None:
    """Creates a ``mujoco.Renderer``, or returns ``None`` if rendering is unavailable."""
    import mujoco

    try:
        renderer = mujoco.Renderer(model, height=height, width=width)
    except Exception as exc:  # GL failures surface as many exception types.
        logger.warning(
            "offscreen rendering unavailable (%s: %s); continuing without video. "
            "Set MUJOCO_GL=egl or MUJOCO_GL=osmesa to enable it.",
            type(exc).__name__,
            exc,
        )
        return None
    return renderer


def render_frame(renderer: Any, data: Any, camera: str = "front") -> NDArray[np.uint8]:
    renderer.update_scene(data, camera=camera)
    return np.asarray(renderer.render(), dtype=np.uint8).copy()


def write_video(frames: Sequence[NDArray[np.uint8]], path: Path, fps: int = 20) -> Path:
    """Writes frames to ``path`` as GIF or MP4, chosen by file suffix.

    MP4 needs the ``imageio-ffmpeg`` package (``pip install robo-evals[video]``).
    If it is missing, the frames are written as a GIF next to the requested path
    and that path is returned instead.
    """
    import imageio.v3 as iio

    if not frames:
        raise ValueError("no frames to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    stack = np.stack(frames)
    if path.suffix == ".mp4":
        try:
            import imageio_ffmpeg  # noqa: F401
        except ImportError:
            logger.warning("imageio-ffmpeg is not installed; writing GIF instead of MP4")
            path = path.with_suffix(".gif")
        else:
            iio.imwrite(path, stack, fps=fps, codec="libx264", macro_block_size=1)
            return path
    if path.suffix != ".gif":
        raise ValueError(f"unsupported video suffix {path.suffix!r}; use .gif or .mp4")
    iio.imwrite(path, stack, duration=1000 / fps, loop=0)
    return path
