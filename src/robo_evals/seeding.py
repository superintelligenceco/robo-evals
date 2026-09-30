"""Deterministic per-episode seed derivation."""

from __future__ import annotations

import zlib

import numpy as np


def episode_seed(base_seed: int, task: str, episode: int) -> int:
    """Derives a stable 32-bit seed for one episode of one task.

    The seed depends only on the base seed, the task name, and the episode
    index, so adding tasks to a run or reordering them never changes the
    scenes an existing task sees.
    """
    if base_seed < 0 or episode < 0:
        raise ValueError("base_seed and episode must be non-negative")
    seq = np.random.SeedSequence([base_seed, zlib.crc32(task.encode("utf-8")), episode])
    return int(seq.generate_state(1, dtype=np.uint32)[0])
