"""Baseline policies shipped with the harness."""

from robo_evals.policies.random import RandomPolicy
from robo_evals.policies.scripted import ScriptedPolicy

__all__ = ["RandomPolicy", "ScriptedPolicy", "random", "scripted", "zero"]


def random() -> RandomPolicy:
    """Factory for the uniform random baseline."""
    return RandomPolicy()


def scripted() -> ScriptedPolicy:
    """Factory for the privileged scripted (oracle) baseline."""
    return ScriptedPolicy()


def zero(obs: object) -> list[float]:
    """A stateless policy that never moves. Useful as a sanity check."""
    return [0.0, 0.0, 0.0, -1.0]
