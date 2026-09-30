# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). Changes that alter success rates for a fixed seed are
called out, because they break comparisons with earlier numbers.

## [Unreleased]

## [0.1.0] - 2026-09-30

The first release: a seeded evaluation harness for manipulation policies in MuJoCo, five tasks,
two baselines, and a remote policy protocol.

### Highlights

- On the `core` suite with 50 episodes per task and base seed 0, the scripted baseline succeeds
  in 250 of 250 episodes (95% Wilson interval 98.5% to 100%) and the random baseline in 0 of 250
  (0% to 1.5%).
- Same seed, same scenes: episode seeds derive from the base seed, task name, and episode index,
  and two runs produce identical reports.

### Added

- Five tasks on a shared table and floating two-finger gripper scene, with MJCF models in the
  package: `reach`, `push`, `pick_place`, `drawer`, and `stack`, each with an explicit success
  predicate. Suites `core` and `smoke`.
- Seeded domain randomization of object and goal poses, friction, and lighting, with the `none`,
  `default`, and `wide` presets.
- `evaluate()` and `robo-evals run`: per-task success rates, Wilson score intervals, mean steps to
  success, and pooled overall results.
- JSON (`robo-evals/report/1`) and Markdown reports, and `robo-evals compare` for side-by-side
  tables.
- Episode videos as GIF or MP4 for the first episode, failures, or every episode, plus optional
  camera image observations.
- Graceful degradation without offscreen rendering: runs still score every episode and the report
  says videos were unavailable. A broken `MUJOCO_GL` backend no longer crashes on import.
- Policy loading from built-in names, `module:attr`, `file.py:attr`, and HTTP or WebSocket URLs.
- The `robo-evals/1` remote protocol, `robo-evals serve`, and a dependency-free example server.
- `random`, `scripted`, and `zero` baseline policies.
- `robo-evals list` to show tasks, suites, and randomization presets.

[Unreleased]: https://github.com/superintelligenceco/robo-evals/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/superintelligenceco/robo-evals/releases/tag/v0.1.0
