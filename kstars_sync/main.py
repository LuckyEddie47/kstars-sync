"""
main.py

CLI entry point for kstars-sync.
"""

from __future__ import annotations

import sys

from kstars_sync.config import load_config
from kstars_sync.workflow import run_workflow


def main() -> None:
    """Entry point for the kstars-sync application."""

    config = load_config()
    exit_code = run_workflow(config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()