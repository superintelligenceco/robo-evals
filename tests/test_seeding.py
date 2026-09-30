from __future__ import annotations

import pytest

from robo_evals.seeding import episode_seed


def test_stable_values() -> None:
    assert episode_seed(0, "reach", 0) == episode_seed(0, "reach", 0)
    assert 0 <= episode_seed(123, "push", 7) < 2**32


def test_seeds_differ_across_inputs() -> None:
    seeds = {episode_seed(b, t, e) for b in (0, 1) for t in ("reach", "push") for e in range(20)}
    assert len(seeds) == 2 * 2 * 20


def test_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        episode_seed(-1, "reach", 0)
