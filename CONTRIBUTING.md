# Contributing to robo-evals

Thanks for helping. This guide shows you how to set up the project, add a task, and open a pull
request.

## Set up

You need Python 3.11 or later.

```sh
git clone https://github.com/superintelligenceco/robo-evals.git
cd robo-evals
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The full test suite takes under a minute on a laptop. Video tests skip automatically when
offscreen rendering is unavailable. To exercise them on headless Linux, install EGL or OSMesa
(for example `apt-get install libosmesa6`) and set `MUJOCO_GL=egl` or `MUJOCO_GL=osmesa`.

## Project layout

| Path | Contents |
| --- | --- |
| `src/robo_evals/assets/` | MJCF models. `common.xml` holds the shared table, lights, cameras, and gripper. |
| `src/robo_evals/env.py` | The `Task` base class: seeding, randomization, stepping, and observations. |
| `src/robo_evals/tasks.py` | The task catalog, success predicates, and suites. |
| `src/robo_evals/randomization.py` | Domain randomization settings and presets. |
| `src/robo_evals/policies/` | The `random` and `scripted` baselines. |
| `src/robo_evals/policy.py` | The policy interface and `--policy` spec loading. |
| `src/robo_evals/remote.py` | HTTP and WebSocket clients and servers. |
| `src/robo_evals/runner.py` | The evaluation loop and result objects. |
| `src/robo_evals/stats.py` | Wilson score intervals. |
| `src/robo_evals/report.py` | JSON and Markdown reports and comparison tables. |
| `src/robo_evals/video.py` | GL backend selection, rendering, and video writing. |
| `src/robo_evals/cli.py` | The `robo-evals` command. |
| `scripts/render_demo.py` | Regenerates `docs/demo.gif`. |

## Checks

Run these before you push. CI runs the same commands on Python 3.11 and 3.12, on Ubuntu and
macOS.

```sh
ruff check .
ruff format --check .
mypy
pytest
```

To fix formatting and safe lint issues automatically, run `ruff format . && ruff check --fix .`.

## Add a task

1. Write an MJCF file in `src/robo_evals/assets/` that includes `common.xml`.
2. Subclass `Task` in `tasks.py`. Set `name`, `xml`, `instruction`, and `max_steps`, and implement
   `_sample_scene` (draw only through `self._uniform` or `self.rng`), `_task_obs`, and
   `is_success`.
3. Register the class in `TASKS` and add it to the `core` suite.
4. Add a controller for it to `ScriptedPolicy`. A task that the scripted policy can't solve
   reliably isn't ready.
5. Add predicate tests to `tests/test_tasks.py`. The parametrized determinism and
   oracle-beats-random tests pick the task up automatically.
6. Regenerate the README results table with `examples/compare_baselines.sh`, and never edit the
   numbers by hand.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages and PR
  titles, for example `feat(tasks): add a peg insertion task`.
- Keep each pull request focused on one change.
- Update `CHANGELOG.md` under `Unreleased` when behavior changes. Changes that move success rates
  for a fixed seed are breaking for anyone comparing numbers, so call them out.

## Releases and artifacts

One workflow ships the project. `release.yml` runs when you push a `v*` tag, and on manual dispatch.
It builds the wheel and sdist, standalone executables for Linux (x86_64 and arm64), macOS (arm64),
and Windows (x86_64), and the multi-arch image on `ghcr.io/superintelligenceco/robo-evals`. It
smoke-tests each of them with a scripted run, scans the image with Trivy, and signs it with cosign.

| Trigger | PyPI | GitHub Release | Image tags |
| --- | --- | --- | --- |
| Tag `v*` pushed | Publishes `robo-evals` | Wheel, sdist, executables, SBOM, `SHA256SUMS`, with provenance attestations | `:vX.Y.Z`, `:latest` |
| `workflow_dispatch` | Nothing | Nothing | `:edge`, `:sha-<short sha>` |

To cut a release, move the `Unreleased` notes in `CHANGELOG.md` under the new version, bump the
version in `pyproject.toml`, `src/robo_evals/__init__.py`, and `CITATION.cff`, then push an
annotated tag:

```sh
git tag -a v0.2.0 -m "robo-evals 0.2.0"
git push origin v0.2.0
```

To dry-run the release from `main` without publishing, run
`gh workflow run release.yml -R superintelligenceco/robo-evals --ref main`.

To build the image locally and run it:

```sh
docker build -t robo-evals:local .
mkdir -p out
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/out:/out" robo-evals:local \
  run --policy scripted --suite smoke --episodes 2 --video first --video-format mp4
```

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree
to uphold it.
