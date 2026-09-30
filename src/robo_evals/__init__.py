"""Reproducible evaluation harness for robot manipulation policies in MuJoCo."""

__version__ = "0.1.0"

from robo_evals.video import configure_gl_backend

# MuJoCo reads MUJOCO_GL when it is first imported, so choose a backend first.
configure_gl_backend()

from robo_evals.policy import Policy, load_policy  # noqa: E402
from robo_evals.randomization import Randomization  # noqa: E402
from robo_evals.runner import EpisodeResult, EvalResult, TaskResult, evaluate  # noqa: E402
from robo_evals.stats import wilson_interval  # noqa: E402
from robo_evals.tasks import SUITES, TASKS, make_task  # noqa: E402

__all__ = [
    "SUITES",
    "TASKS",
    "EpisodeResult",
    "EvalResult",
    "Policy",
    "Randomization",
    "TaskResult",
    "__version__",
    "evaluate",
    "load_policy",
    "make_task",
    "wilson_interval",
]
