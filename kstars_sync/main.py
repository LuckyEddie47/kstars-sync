"""
main.py

CLI entry point for kstars-sync.
"""

from __future__ import annotations

import sys
import termios
import tty

from kstars_sync.config import load_config
from kstars_sync.workflow import run_workflow


def wait_for_exit() -> None:
    """
    Pause before closing an interactive terminal.

    When stdin is attached to a terminal, wait for a single keypress without
    requiring Enter. In non-interactive environments, display the completion
    message but do not block.
    """

    print(
        "\nkstars-sync completed, press any key to exit...",
        end="",
        flush=True,
    )

    if not sys.stdin.isatty():
        print()
        return

    file_descriptor = sys.stdin.fileno()
    original_settings = termios.tcgetattr(file_descriptor)

    try:
        tty.setraw(file_descriptor)
        sys.stdin.read(1)
    finally:
        termios.tcsetattr(
            file_descriptor,
            termios.TCSADRAIN,
            original_settings,
        )

    print()


def main() -> None:
    """Entry point for the kstars-sync application."""

    config = load_config()
    exit_code = run_workflow(config)
    wait_for_exit()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
