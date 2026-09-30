# FAQ

## Why do two runs give the same numbers?

Every episode seed comes from the base seed, the task name, and the episode index, so the scenes
do not depend on run order or on how many episodes you ask for. The random baseline draws from
the episode seed too. See [ADR 0001](adr/0001-hash-derived-episode-seeds.md).

## Are results identical across machines?

Only for the same robo-evals version, MuJoCo version, and platform. MuJoCo does not promise
bit-identical physics across versions or CPU architectures. Each report records the versions and
the platform, so pin `mujoco` when you publish numbers.

## Why Wilson intervals instead of a plus-or-minus?

A normal approximation breaks down at 0% and 100%, which are exactly the rates a baseline
often scores. The Wilson interval stays inside 0 to 1 and behaves for small samples. See
[ADR 0002](adr/0002-wilson-score-intervals.md).

## Does it need a GPU?

No. Scoring needs no rendering at all. Videos need an OpenGL context; on headless Linux install
EGL or OSMesa, or use the container image, which ships OSMesa.

## What happens when rendering is unavailable?

The harness logs a warning, skips videos, scores every episode, and states in the report that
videos were unavailable. Image observations fail loudly instead, because a vision policy cannot
run without them.

## Can I evaluate a model that needs its own environment?

Yes. Serve it over HTTP or WebSocket and pass its URL to `--policy`. See the
[protocol](protocol.md) and [ADR 0003](adr/0003-remote-policy-protocol.md).

## Does the scripted policy count as a result?

No. It reads ground-truth object positions, so it is an upper bound that shows each task is
solvable, not a learned policy.

## How do I cite it?

Use the metadata in `CITATION.cff` at the root of the repository.
