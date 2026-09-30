#!/usr/bin/env bash
# Records docs/cli-demo.gif: a real terminal session with the robo-evals CLI.
#
# Needs asciinema (pip install asciinema) and agg (github.com/asciinema/agg),
# and robo-evals on PATH. Run from the repository root:
#
#   scripts/record_demo.sh
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

cat > "$work/session.sh" <<'SESSION'
#!/usr/bin/env bash
set -euo pipefail
# Hide Mesa driver warnings on headless hosts; they are noise, not robo-evals output.
export EGL_LOG_LEVEL=fatal
type_run() {
  printf '\033[1;32m$\033[0m '
  local text="$*"
  for ((i = 0; i < ${#text}; i++)); do
    printf '%s' "${text:i:1}"
    sleep 0.02
  done
  printf '\n'
  eval "$*"
  sleep 1.2
}
type_run robo-evals --version
type_run robo-evals list
type_run robo-evals run --policy random --suite smoke --episodes 10 --quiet '>' /dev/null
type_run robo-evals run --policy scripted --suite smoke --episodes 10 --video first --quiet '>' /dev/null
type_run ls results/scripted results/scripted/videos
type_run robo-evals compare results/random/report.json results/scripted/report.json
sleep 2
SESSION
chmod +x "$work/session.sh"

cd "$work"
asciinema rec --overwrite --cols 100 --rows 30 -c "$work/session.sh" "$work/demo.cast"
agg --font-family "${AGG_FONT_FAMILY:-JetBrains Mono,Fira Code,DejaVu Sans Mono,Source Code Pro}" \
  --font-size 16 --idle-time-limit 2 "$work/demo.cast" "$root/docs/cli-demo.gif"
echo "wrote docs/cli-demo.gif"
