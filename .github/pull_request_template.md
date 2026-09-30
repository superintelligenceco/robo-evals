## Summary

<!-- What does this change and why? Link the issue it fixes, for example "Fixes #12". -->

## Checklist

- [ ] `ruff check .`, `ruff format --check .`, `mypy`, and `pytest` pass locally.
- [ ] A new or changed task has predicate tests and passes the oracle-beats-random test in `tests/test_e2e.py`.
- [ ] If the change can move success rates, the README results table is regenerated with `examples/compare_baselines.sh`.
- [ ] `CHANGELOG.md` is updated if behavior changed.
- [ ] The PR title follows [Conventional Commits](https://www.conventionalcommits.org/).
