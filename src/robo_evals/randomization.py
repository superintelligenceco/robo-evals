"""Seeded domain randomization knobs.

Every random draw in an episode comes from a single ``numpy.random.Generator``
created from the episode seed, so the same seed always produces the same scene.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Randomization:
    """Controls how much each episode's scene varies.

    Attributes:
        object_pose: Scale in ``[0, 1]`` applied to each task's object and goal
            placement ranges. ``0`` places everything at the range centers.
        friction: ``(low, high)`` multiplier applied to the sliding friction of
            every geom. ``(1.0, 1.0)`` disables friction randomization.
        lighting: Whether to randomize light direction, intensity, and ambient
            level. Lighting only affects rendered images, never physics.
    """

    object_pose: float = 1.0
    friction: tuple[float, float] = (0.8, 1.2)
    lighting: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.object_pose <= 1.0:
            raise ValueError(f"object_pose must be in [0, 1], got {self.object_pose}")
        low, high = self.friction
        if not 0.0 < low <= high:
            raise ValueError(f"friction range must satisfy 0 < low <= high, got {self.friction}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PRESETS: dict[str, Randomization] = {
    "none": Randomization(object_pose=0.0, friction=(1.0, 1.0), lighting=False),
    "default": Randomization(),
    "wide": Randomization(object_pose=1.0, friction=(0.6, 1.4), lighting=True),
}


def get_preset(name: str) -> Randomization:
    """Returns a named randomization preset."""
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(
            f"unknown randomization preset {name!r}; choose from {sorted(PRESETS)}"
        ) from None
