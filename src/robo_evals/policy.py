"""The policy interface and policy loading.

A policy is any callable that maps an observation to an action::

    def my_policy(obs: dict) -> list[float]:  # [dx, dy, dz, grip] in [-1, 1]
        ...

It may also define ``reset(task: str, seed: int)``, which the harness calls
before every episode.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from numpy.typing import ArrayLike

BUILTIN = {
    "random": "robo_evals.policies:random",
    "scripted": "robo_evals.policies:scripted",
    "zero": "robo_evals.policies:zero",
}


@runtime_checkable
class Policy(Protocol):
    """Maps an observation to an action ``[dx, dy, dz, grip]`` in ``[-1, 1]``."""

    def __call__(self, obs: Mapping[str, Any]) -> ArrayLike: ...


def reset_policy(policy: Policy, task: str, seed: int) -> None:
    """Calls ``policy.reset(task, seed)`` if the policy defines it."""
    reset = getattr(policy, "reset", None)
    if callable(reset):
        reset(task, seed)


def close_policy(policy: Policy) -> None:
    close = getattr(policy, "close", None)
    if callable(close):
        close()


def _import_target(module_name: str) -> Any:
    if module_name.endswith(".py") or "/" in module_name:
        path = Path(module_name).resolve()
        if not path.is_file():
            raise ValueError(f"policy file not found: {module_name}")
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot import policy file {module_name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(module_name)


def _is_factory(obj: Any) -> bool:
    """True for classes and for callables that take no required arguments."""
    if inspect.isclass(obj):
        return True
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return False
    required = [
        p
        for p in sig.parameters.values()
        if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    return not required


def load_policy(spec: str) -> Policy:
    """Resolves a policy spec into a callable policy.

    Accepted specs:

    * ``random``, ``scripted``, ``zero``: built-in baselines.
    * ``http://host:port`` or ``ws://host:port``: a remote policy server.
    * ``package.module:attr`` or ``path/to/file.py:attr``: a Python object. If
      ``attr`` is a class or a callable with no required arguments, the harness
      calls it once to build the policy. Otherwise ``attr`` is the policy.
    """
    spec = BUILTIN.get(spec, spec)
    if spec.startswith(("http://", "https://", "ws://", "wss://")):
        from robo_evals.remote import connect

        return connect(spec)
    module_name, sep, attr = spec.rpartition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"policy spec must look like 'module:attr', got {spec!r}")
    module = _import_target(module_name)
    try:
        obj = getattr(module, attr)
    except AttributeError:
        raise ValueError(f"{module_name!r} has no attribute {attr!r}") from None
    policy = obj() if _is_factory(obj) else obj
    if not callable(policy):
        raise TypeError(f"policy {spec!r} is not callable")
    return policy  # type: ignore[no-any-return]
