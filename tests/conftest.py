"""Shared fixtures."""

from __future__ import annotations

import pytest

import robo_evals  # noqa: F401  (configures the GL backend before mujoco loads)
from robo_evals.video import try_make_renderer


@pytest.fixture(scope="session")
def can_render() -> bool:
    """True when offscreen rendering works in this environment."""
    from robo_evals.tasks import make_task

    renderer = try_make_renderer(make_task("reach").model, 64, 48)
    if renderer is None:
        return False
    renderer.close()
    return True
