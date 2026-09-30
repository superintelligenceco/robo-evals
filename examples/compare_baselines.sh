#!/usr/bin/env bash
# Reproduces the baseline table in the README.
set -euo pipefail
episodes="${EPISODES:-50}"
seed="${SEED:-0}"
out="${OUT:-results}"
for policy in random scripted; do
  robo-evals run --policy "$policy" --suite core --episodes "$episodes" --seed "$seed" \
    --out "$out" --quiet > /dev/null
done
robo-evals compare "$out/random/report.json" "$out/scripted/report.json"
