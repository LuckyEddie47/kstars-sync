"""
session.py

Git workflow decision handling and cleanup execution for kstars-sync.
"""

from __future__ import annotations

import socket
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from kstars_sync import prompts
from kstars_sync.git_manager import GitError, GitManager


class CleanupAction(Enum):
    """Actions available when local changes exist after KStars exits."""

    COMMIT = auto()
    STASH = auto()
    DISCARD = auto()
    DO_NOTHING = auto()


def generate_default_commit_message(
    hostname: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """
    Generate a default commit message containing hostname and timestamp.
    """

    if hostname is None:
        hostname = socket.gethostname()

    if now is None:
        now = datetime.now()

    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    return f"{hostname} {timestamp}"


def pre_launch_sync(
    git_manager: GitManager,
    continue_without_fetch: bool = False,
) -> bool:
    """
    Perform pre-launch synchronization (fetch and fast-forward pull).

    Returns
    -------
    bool
        True if the workflow should proceed to launch KStars, False if aborted.
    """

    try:
        git_manager.fetch()
    except GitError as ex:
        print(f"Git fetch failed: {ex}")

        if not continue_without_fetch:
            if not prompts.confirm("Git fetch failed. Continue anyway?"):
                return False

    ahead_count = git_manager.remote_ahead_count()

    if ahead_count > 0:
        summary = git_manager.remote_commit_summary()
        prompts.show_summary(
            f"Upstream is ahead by {ahead_count} commit(s):",
            summary,
        )

        if prompts.confirm("Pull changes from upstream?"):
            try:
                git_manager.pull()
            except GitError as ex:
                print(f"Pull failed: {ex}")
                if not prompts.confirm("Continue launching KStars anyway?"):
                    return False

    return True


def should_proceed_after_exit(returncode: int) -> bool:
    """
    Determine whether to proceed to Git cleanup based on KStars exit status.
    """

    if returncode == 0:
        return True

    return prompts.confirm(
        f"KStars exited with status {returncode}. Continue to Git cleanup?"
    )


def post_launch_cleanup(git_manager: GitManager) -> None:
    """
    Perform post-launch cleanup if local modifications exist.
    """

    if not git_manager.has_local_changes():
        return

    summary = git_manager.diff_summary()
    prompts.show_summary("Local changes detected:", summary)

    options = [
        "Commit and push changes",
        "Stash changes",
        "Discard local changes",
        "Do nothing",
    ]

    choice = prompts.choose_action("Select a cleanup action:", options)
    action = list(CleanupAction)[choice]

    if action == CleanupAction.COMMIT:
        default_msg = generate_default_commit_message()
        commit_msg = prompts.request_commit_message(default_msg)

        git_manager.add_all()
        git_manager.commit(commit_msg)
        git_manager.push()

    elif action == CleanupAction.STASH:
        git_manager.stash()

    elif action == CleanupAction.DISCARD:
        git_manager.restore()

    elif action == CleanupAction.DO_NOTHING:
        pass