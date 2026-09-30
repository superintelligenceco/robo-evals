"""Evaluate two policies from Python and print a comparison table."""

from __future__ import annotations

from robo_evals import evaluate, load_policy
from robo_evals.report import compare_markdown


def main() -> None:
    reports = []
    for name in ("random", "scripted"):
        result = evaluate(load_policy(name), suite="smoke", episodes=5, seed=0, policy_name=name)
        reports.append(result.to_dict())
    print(compare_markdown(reports))


if __name__ == "__main__":
    main()
