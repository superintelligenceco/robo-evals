#!/bin/sh
# Installs the standalone robo-evals executable from a GitHub Release.
#
#   curl -fsSL https://raw.githubusercontent.com/superintelligenceco/robo-evals/main/install.sh | sh
#
# Environment variables:
#   ROBO_EVALS_VERSION      release tag to install, for example v0.2.0 (default: latest)
#   ROBO_EVALS_INSTALL_DIR  where to put the executable (default: $HOME/.local/bin)
#
# The script picks the archive for this OS and CPU, checks it against the
# release's SHA256SUMS, and installs one file: robo-evals.
set -eu

REPO="superintelligenceco/robo-evals"
VERSION="${ROBO_EVALS_VERSION:-latest}"
INSTALL_DIR="${ROBO_EVALS_INSTALL_DIR:-$HOME/.local/bin}"

say() { printf 'robo-evals install: %s\n' "$*" >&2; }
fail() { say "error: $*"; exit 1; }

need() { command -v "$1" > /dev/null 2>&1 || fail "$1 is required"; }
need uname
need tar
need mktemp

if command -v curl > /dev/null 2>&1; then
  fetch() { curl -fsSL --retry 3 -o "$2" "$1"; }
elif command -v wget > /dev/null 2>&1; then
  fetch() { wget -q -O "$2" "$1"; }
else
  fail "curl or wget is required"
fi

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=macos ;;
  *) fail "unsupported OS $(uname -s); install from PyPI instead: pip install robo-evals" ;;
esac

case "$(uname -m)" in
  x86_64 | amd64) arch=x86_64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) fail "unsupported CPU $(uname -m); install from PyPI instead: pip install robo-evals" ;;
esac

if [ "$os" = macos ] && [ "$arch" = x86_64 ]; then
  fail "no Intel macOS build; install from PyPI instead: pip install robo-evals"
fi

asset="robo-evals-${os}-${arch}.tar.gz"
if [ "$VERSION" = latest ]; then
  base="https://github.com/${REPO}/releases/latest/download"
else
  base="https://github.com/${REPO}/releases/download/${VERSION}"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

say "downloading ${asset} (${VERSION})"
fetch "${base}/${asset}" "${tmp}/${asset}" || fail "could not download ${base}/${asset}"
fetch "${base}/SHA256SUMS" "${tmp}/SHA256SUMS" || fail "could not download SHA256SUMS"

expected="$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1 }' "${tmp}/SHA256SUMS")"
[ -n "$expected" ] || fail "${asset} is not listed in SHA256SUMS"
if command -v sha256sum > /dev/null 2>&1; then
  actual="$(sha256sum "${tmp}/${asset}" | awk '{ print $1 }')"
elif command -v shasum > /dev/null 2>&1; then
  actual="$(shasum -a 256 "${tmp}/${asset}" | awk '{ print $1 }')"
else
  fail "sha256sum or shasum is required to verify the download"
fi
[ "$expected" = "$actual" ] || fail "checksum mismatch for ${asset}"

tar -xzf "${tmp}/${asset}" -C "$tmp" robo-evals
mkdir -p "$INSTALL_DIR"
mv "${tmp}/robo-evals" "${INSTALL_DIR}/robo-evals"
chmod 755 "${INSTALL_DIR}/robo-evals"

say "installed $("${INSTALL_DIR}/robo-evals" --version) to ${INSTALL_DIR}/robo-evals"
case ":${PATH}:" in
  *":${INSTALL_DIR}:"*) ;;
  *) say "add ${INSTALL_DIR} to your PATH to run robo-evals from anywhere" ;;
esac
