"""
workflow.py

Main workflow orchestration for kstars-sync.
"""

from __future__ import annotations

import sys

from kstars_sync import process, session
from kstars_sync.config import (
    Config,
    ConfigError,
    RuntimeValidationError,
    validate_config,
    validate_runtime,
)
from kstars_sync.git_manager import GitError, GitManager
from kstars_sync.process import ProcessError


def run_workflow(config: Config) -> int:
    """
    Orchestrate the application lifecycle.

    Parameters
    ----------
    config
        Application configuration settings.

    Returns
    -------
    int
        Process exit status (0 for success, non-zero for error/cancellation).
    """

    try:
        validate_runtime()
        validate_config(config)
    except (ConfigError, RuntimeValidationError) as ex:
        print(f"Configuration error: {ex}", file=sys.stderr)
        return 1

    git_manager = GitManager(config.repo, verbose=config.verbose)

    try:
        git_manager.validate_repository()
    except GitError as ex:
        print(f"Repository error: {ex}", file=sys.stderr)
        return 1

    if process.is_running(config.kstars):
        print(
            f"KStars is already running ({config.kstars}).",
            file=sys.stderr,
        )
        return 1

    if config.dry_run:
        print("[DRY RUN] Configuration and repository validation passed.")
        print(f"[DRY RUN] Repository path: {config.repo}")
        print(f"[DRY RUN] KStars executable path: {config.kstars}")
        print("[DRY RUN] Workflow completed without applying changes.")
        return 0

    if not session.pre_launch_sync(
        git_manager,
        continue_without_fetch=config.continue_without_fetch,
    ):
        print("Pre-launch sync aborted.", file=sys.stderr)
        return 1

    try:
        app_result = process.run_application(config.kstars)
    except ProcessError as ex:
        print(f"Failed to launch KStars: {ex}", file=sys.stderr)
        return 1

    if not session.should_proceed_after_exit(app_result.returncode):
        print("Post-launch cleanup skipped.", file=sys.stderr)
        return app_result.returncode

    try:
        session.post_launch_cleanup(git_manager)
    except GitError as ex:
        print(f"Error during post-launch cleanup: {ex}", file=sys.stderr)
        return 1

    return 0