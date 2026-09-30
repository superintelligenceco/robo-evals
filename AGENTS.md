# AGENTS.md

Guidance for coding agents that work in this repository.

## Commands

- Install: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
- Lint: `ruff check .` and `ruff format --check .`. Fix with `ruff format . && ruff check --fix .`.
- Typecheck: `mypy` (strict, configured in `pyproject.toml`)
- Test: `pytest`
- Try it: `robo-evals run --policy scripted --suite smoke --episodes 5`

Run lint, typecheck, and test before you finish a change. All must pass.

## Conventions

- Python 3.11 or later, `from __future__ import annotations` in every module, full type hints.
- Runtime dependencies are `mujoco`, `numpy`, `imageio`, and `pillow`. Ask before adding one.
- `robo_evals/__init__.py` must configure the GL backend before anything imports `mujoco`.
- All randomness in a task goes through `self.rng` (seeded in `reset`). Never use the global NumPy
  random state or `random`.
- A new random draw shifts every later draw in the episode, which changes results for existing
  seeds. Append new draws after existing ones and note the change in `CHANGELOG.md`.
- Commit messages follow Conventional Commits.

## Boundaries

- Don't commit `.venv/`, `dist/`, `results/`, videos, or coverage output. The only committed media
  is `docs/demo.gif`, regenerated with `scripts/render_demo.py`.
- Don't edit the README results table by hand. Regenerate it with `examples/compare_baselines.sh`.
- Don't weaken a test to make it pass. Fix the code or explain why the test was wrong.
- Don't put secrets, tokens, or machine-specific paths in fixtures or examples.
