"""Fails when the evaluation loop gets slower than the gate allows.

Reads a pytest-benchmark JSON file and checks two things, both measured in the
same process, so the gate holds on any machine:

- Harness overhead: the fastest ``Task.step`` time divided by the fastest raw
  physics time for the same control step (25 MuJoCo substeps). The harness adds
  action clipping, the gripper controller, and the observation dictionary; it
  must stay below ``MAX_OVERHEAD`` times the physics it wraps. The minimum is
  the least noisy statistic on a shared CI runner.
- Absolute floors on the cheap helpers, far above their normal cost, which only
  trip on an accidental quadratic or a per-call import.

Usage::

    python scripts/bench_gate.py bench.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_OVERHEAD = 2.0
MAX_MEDIAN_SECONDS = {
    "test_bench_wilson_interval": 1e-4,
    "test_bench_episode_seed": 1e-3,
    "test_bench_task_reset": 5e-2,
}


def main(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    median = {b["name"]: b["stats"]["median"] for b in data["benchmarks"]}
    fastest = {b["name"]: b["stats"]["min"] for b in data["benchmarks"]}
    failures = []

    ratio = fastest["test_bench_task_step"] / fastest["test_bench_raw_physics_control_step"]
    print("| Check | Value | Limit | Result |")
    print("| --- | --- | --- | --- |")
    ok = ratio <= MAX_OVERHEAD
    print(f"| step overhead vs raw physics | {ratio:.2f}x | {MAX_OVERHEAD:.2f}x | {_mark(ok)} |")
    if not ok:
        failures.append("step overhead")

    for name, limit in MAX_MEDIAN_SECONDS.items():
        value = median[name]
        ok = value <= limit
        print(f"| {name} median | {value * 1e6:.1f} us | {limit * 1e6:.0f} us | {_mark(ok)} |")
        if not ok:
            failures.append(name)

    if failures:
        print(f"\nBenchmark gate failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def _mark(ok: bool) -> str:
    return "pass" if ok else "FAIL"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: bench_gate.py bench.json")
    raise SystemExit(main(sys.argv[1]))
