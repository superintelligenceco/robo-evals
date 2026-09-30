from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from robo_evals.policies import RandomPolicy, ScriptedPolicy, zero
from robo_evals.policy import load_policy, reset_policy


def test_builtin_names() -> None:
    assert isinstance(load_policy("random"), RandomPolicy)
    assert isinstance(load_policy("scripted"), ScriptedPolicy)
    assert load_policy("zero") is zero


def test_module_attr_factory_and_callable() -> None:
    assert isinstance(load_policy("robo_evals.policies:RandomPolicy"), RandomPolicy)
    assert load_policy("robo_evals.policies:zero") is zero


def test_file_spec(tmp_path: Path) -> None:
    f = tmp_path / "my_policy.py"
    f.write_text(
        "class Up:\n"
        "    def __call__(self, obs):\n"
        "        return [0, 0, 1, -1]\n"
        "def act(obs, extra=None):\n"
        "    return [1, 0, 0, -1]\n"
    )
    up = load_policy(f"{f}:Up")
    assert list(up({})) == [0, 0, 1, -1]
    # ``act`` needs an argument, so it is the policy itself, not a factory.
    assert load_policy(f"{f}:act") is not None


@pytest.mark.parametrize(
    ("spec", "error"),
    [
        ("no_colon", ValueError),
        ("robo_evals.policies:does_not_exist", ValueError),
        ("missing/file.py:act", ValueError),
        ("robo_evals:__version__", TypeError),
    ],
)
def test_bad_specs(spec: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        load_policy(spec)


def test_random_policy_is_seeded() -> None:
    a, b = RandomPolicy(), RandomPolicy()
    reset_policy(a, "reach", 5)
    reset_policy(b, "reach", 5)
    obs: dict[str, Any] = {}
    np.testing.assert_array_equal(a(obs), b(obs))
    out = a(obs)
    assert out.shape == (4,)
    assert np.all(np.abs(out) <= 1.0)


def test_reset_policy_ignores_missing_reset() -> None:
    reset_policy(zero, "reach", 0)


def test_scripted_rejects_unknown_task() -> None:
    p = ScriptedPolicy()
    p.reset("unknown", 0)
    with pytest.raises(ValueError, match="no controller"):
        p({"ee_pos": np.zeros(3)})
