"""Fails when the mutation score drops below the gate.

Reads the output of ``mutmut results --all true`` on standard input and computes
killed / (killed + survived). The gate sits a few points under the measured score,
so it catches a real loss of test strength but not noise::

    mutmut results --all true | python scripts/mutation_gate.py
"""

from __future__ import annotations

import sys

MIN_SCORE = 0.60


def main(text: str) -> int:
    killed = survived = 0
    for line in text.splitlines():
        status = line.strip().rsplit(" ", 1)[-1]
        killed += status == "killed"
        survived += status == "survived"
    total = killed + survived
    if total == 0:
        print("no mutation results found", file=sys.stderr)
        return 1
    score = killed / total
    print(f"mutation score {score:.1%} ({killed} killed, {survived} survived of {total})")
    if score < MIN_SCORE:
        print(f"below the {MIN_SCORE:.0%} gate", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.stdin.read()))
