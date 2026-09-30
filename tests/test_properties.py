"""Property-based tests for the statistics, seeding, and randomization logic."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from robo_evals.randomization import Randomization
from robo_evals.seeding import episode_seed
from robo_evals.stats import wilson_interval, z_for_confidence
from robo_evals.tasks import TASKS, make_task

confidences = st.floats(min_value=0.5, max_value=0.999, allow_nan=False)


@st.composite
def counts(draw: st.DrawFn) -> tuple[int, int]:
    trials = draw(st.integers(min_value=0, max_value=10_000))
    successes = draw(st.integers(min_value=0, max_value=trials))
    return successes, trials


@given(counts(), confidences)
def test_wilson_interval_is_a_valid_interval_around_the_rate(
    kn: tuple[int, int], confidence: float
) -> None:
    k, n = kn
    low, high = wilson_interval(k, n, confidence)
    assert 0.0 <= low <= high <= 1.0
    if n:
        p = k / n
        assert low <= p + 1e-12
        assert p - 1e-12 <= high


@given(counts())
def test_wilson_interval_is_pinned_at_the_extremes(kn: tuple[int, int]) -> None:
    k, n = kn
    low, high = wilson_interval(k, n)
    if k == 0:
        assert low == 0.0
    if k == n:
        assert high == 1.0


@given(counts())
def test_wilson_interval_is_symmetric_under_swapping_success_and_failure(
    kn: tuple[int, int],
) -> None:
    k, n = kn
    low, high = wilson_interval(k, n)
    flow, fhigh = wilson_interval(n - k, n)
    assert math.isclose(low, 1.0 - fhigh, abs_tol=1e-9)
    assert math.isclose(high, 1.0 - flow, abs_tol=1e-9)


@given(counts(), confidences, confidences)
def test_higher_confidence_never_narrows_the_interval(
    kn: tuple[int, int], c1: float, c2: float
) -> None:
    k, n = kn
    lo_c, hi_c = sorted((c1, c2))
    narrow = wilson_interval(k, n, lo_c)
    wide = wilson_interval(k, n, hi_c)
    assert wide[0] <= narrow[0] + 1e-12
    assert wide[1] >= narrow[1] - 1e-12


@given(st.integers(min_value=1, max_value=2_000), st.data())
def test_more_episodes_at_the_same_rate_narrow_the_interval(n: int, data: st.DataObject) -> None:
    k = data.draw(st.integers(min_value=0, max_value=n))
    low, high = wilson_interval(k, n)
    low4, high4 = wilson_interval(4 * k, 4 * n)
    assert high4 - low4 <= high - low + 1e-12


@given(st.floats(min_value=1e-6, max_value=1 - 1e-6))
def test_z_grows_with_confidence(c: float) -> None:
    assert z_for_confidence(c) >= 0.0
    assert z_for_confidence(min(c + 1e-3, 1 - 1e-9)) >= z_for_confidence(c)


@given(st.integers(min_value=0, max_value=10_000))
def test_wilson_rejects_more_successes_than_trials(n: int) -> None:
    with pytest.raises(ValueError, match="successes"):
        wilson_interval(n + 1, n)


seeds = st.integers(min_value=0, max_value=2**63 - 1)
episodes = st.integers(min_value=0, max_value=100_000)
task_names = st.text(min_size=1, max_size=30)


@given(seeds, task_names, episodes)
def test_episode_seed_is_a_deterministic_uint32(base: int, task: str, ep: int) -> None:
    s = episode_seed(base, task, ep)
    assert s == episode_seed(base, task, ep)
    assert 0 <= s < 2**32


@settings(max_examples=50)
@given(seeds, task_names, st.lists(episodes, min_size=2, max_size=20, unique=True))
def test_episode_seeds_rarely_collide_within_a_task(base: int, task: str, eps: list[int]) -> None:
    got = {episode_seed(base, task, e) for e in eps}
    # 32-bit seeds: a collision among 20 draws has probability below 1e-7.
    assert len(got) == len(eps)


@given(st.integers(max_value=-1), task_names, episodes)
def test_episode_seed_rejects_negative_base_seeds(base: int, task: str, ep: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        episode_seed(base, task, ep)


@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.floats(min_value=1e-3, max_value=10.0),
    st.floats(min_value=0.0, max_value=10.0),
    st.booleans(),
)
def test_valid_randomization_round_trips_through_to_dict(
    pose: float, low: float, extra: float, lighting: bool
) -> None:
    r = Randomization(object_pose=pose, friction=(low, low + extra), lighting=lighting)
    assert Randomization(**r.to_dict()) == r


@given(st.floats(allow_nan=False).filter(lambda x: not 0.0 <= x <= 1.0))
def test_randomization_rejects_out_of_range_object_pose(pose: float) -> None:
    with pytest.raises(ValueError, match="object_pose"):
        Randomization(object_pose=pose)


@given(st.floats(min_value=0.01, max_value=10.0), st.floats(min_value=1e-3, max_value=5.0))
def test_randomization_rejects_inverted_friction_ranges(high: float, gap: float) -> None:
    with pytest.raises(ValueError, match="friction"):
        Randomization(friction=(high + gap, high))


@settings(max_examples=25, deadline=None)
@given(st.sampled_from(sorted(TASKS)), st.integers(min_value=0, max_value=2**32 - 1))
def test_a_task_reset_is_a_pure_function_of_its_seed(name: str, seed: int) -> None:
    a = make_task(name).reset(seed)
    b = make_task(name).reset(seed)
    assert a.keys() == b.keys()
    for key, value in a.items():
        if key == "instruction":
            assert value == b[key]
        else:
            assert np.array_equal(value, b[key]), key
