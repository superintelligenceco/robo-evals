"""PyInstaller entry point for the standalone ``robo-evals`` executable."""

import sys

from robo_evals.cli import main

if __name__ == "__main__":
    sys.exit(main())
