"""Builds the standalone ``robo-evals`` executable with PyInstaller.

The executable bundles Python, MuJoCo, NumPy, the task models, PyOpenGL, and
ffmpeg, so it runs without a Python install. It writes one archive to
``dist-bin/``, named for the platform, for example
``robo-evals-linux-x86_64.tar.gz`` or ``robo-evals-windows-x86_64.zip``.

Run from the repository root, in an environment with robo-evals installed
(``pip install ".[video,ws]" pyinstaller``)::

    python scripts/build_binary.py
"""

from __future__ import annotations

import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist-bin"
ARCH_NAMES = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}


def platform_tag() -> str:
    """Returns ``<os>-<arch>``, for example ``linux-arm64``."""
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
    if system.startswith("linux"):
        system = "linux"
    machine = platform.machine().lower()
    return f"{system}-{ARCH_NAMES.get(machine, machine)}"


def build() -> Path:
    import PyInstaller.__main__

    work = ROOT / "build" / "pyinstaller"
    PyInstaller.__main__.run(
        [
            str(ROOT / "packaging" / "entry.py"),
            "--onefile",
            "--noconfirm",
            "--clean",
            "--log-level=WARN",
            "--name=robo-evals",
            f"--distpath={work / 'dist'}",
            f"--workpath={work / 'build'}",
            f"--specpath={work}",
            "--collect-all=mujoco",
            "--collect-data=robo_evals",
            "--collect-submodules=robo_evals",
            "--collect-submodules=OpenGL",
            # Collected by name, because importing a GL backend that has no
            # system library at build time fails and PyInstaller skips it.
            "--hidden-import=mujoco.egl",
            "--hidden-import=mujoco.osmesa",
            "--hidden-import=mujoco.cgl",
            "--collect-submodules=websockets",
            "--collect-all=imageio_ffmpeg",
            "--copy-metadata=imageio",
            "--copy-metadata=robo-evals",
            "--exclude-module=tkinter",
        ]
    )
    exe = work / "dist" / ("robo-evals.exe" if sys.platform == "win32" else "robo-evals")
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}")
    return exe


def archive(exe: Path) -> Path:
    OUT.mkdir(exist_ok=True)
    stem = f"robo-evals-{platform_tag()}"
    if sys.platform == "win32":
        path = OUT / f"{stem}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe, exe.name)
            zf.write(ROOT / "LICENSE", "LICENSE")
    else:
        path = OUT / f"{stem}.tar.gz"
        with tarfile.open(path, "w:gz") as tf:
            tf.add(exe, exe.name)
            tf.add(ROOT / "LICENSE", "LICENSE")
    return path


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    path = archive(build())
    print(path)


if __name__ == "__main__":
    main()
