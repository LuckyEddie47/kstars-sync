"""
session.py

Git workflow decision handling and cleanup execution for kstars-sync.
"""

from __future__ import annotations

import shutil
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from kstars_sync import prompts
from kstars_sync.git_manager import GitError, GitManager
from kstars_sync.sqlite_compare import (
    SQLiteCompareError,
    changed_tables,
    logically_identical,
)
from kstars_sync.userdb_report import format_changed_tables


class SessionError(Exception):
    """Raised when session preparation or cleanup cannot be completed safely."""


@dataclass(slots=True)
class DatabaseSnapshot:
    """Temporary preserved copy of a database used during one KStars session."""

    source: Path
    copy: Path
    _temporary_directory: tempfile.TemporaryDirectory

    def cleanup(self) -> None:
        """Remove the temporary snapshot directory and its contents."""
        self._temporary_directory.cleanup()


class CleanupAction(Enum):
    """Actions available when local changes exist after KStars exits."""

    COMMIT = auto()
    STASH = auto()
    DISCARD = auto()
    DO_NOTHING = auto()


def preserve_database(
    repo: Path | str,
    filename: str,
) -> DatabaseSnapshot:
    """
    Preserve a repository database in a temporary directory.

    Parameters
    ----------
    repo
        Repository containing the database.

    filename
        Database filename relative to the repository root. Nested paths and
        absolute paths are not accepted.

    The returned snapshot remains available until ``cleanup()`` is called.
    The source database is not modified.

    Raises
    ------
    SessionError
        If the filename is invalid, the database does not exist, is not a
        regular file, or cannot be copied safely.
    """

    relative = Path(filename)

    if (
        relative.is_absolute()
        or len(relative.parts) != 1
        or relative.name in ("", ".", "..")
    ):
        raise SessionError(
            f"Database filename must be a single relative filename: {filename}"
        )

    source = Path(repo) / relative.name

    if not source.exists():
        raise SessionError(f"{relative.name} does not exist: {source}")

    if not source.is_file():
        raise SessionError(f"{relative.name} is not a file: {source}")

    temporary_directory = tempfile.TemporaryDirectory(
        prefix="kstars-sync-"
    )
    copy = Path(temporary_directory.name) / relative.name

    try:
        shutil.copy2(source, copy)
    except OSError as ex:
        temporary_directory.cleanup()
        raise SessionError(
            f"Failed to preserve {relative.name} '{source}': {ex}"
        ) from ex

    return DatabaseSnapshot(
        source=source,
        copy=copy,
        _temporary_directory=temporary_directory,
    )


def preserve_userdb(repo: Path | str) -> DatabaseSnapshot:
    """Preserve the repository's userdb.sqlite database."""
    return preserve_database(repo, "userdb.sqlite")


def reconcile_database(snapshot: DatabaseSnapshot) -> bool:
    """
    Remove non-logical SQLite churn from a preserved database.

    The preserved pre-launch database is compared logically with the live
    post-launch database. If they are logically identical, the preserved copy
    is copied back over the live database so incidental SQLite file/header
    changes do not appear in Git.

    If the databases differ logically, the live database is left untouched.

    Returns
    -------
    bool
        True if the preserved database was restored, False if genuine logical
        differences were detected.

    Raises
    ------
    SessionError
        If comparison cannot be completed safely or restoration fails.
    """

    database_name = snapshot.source.name

    try:
        identical = logically_identical(snapshot.copy, snapshot.source)
    except SQLiteCompareError as ex:
        raise SessionError(
            f"Failed to compare {database_name} with its preserved copy: {ex}"
        ) from ex

    if not identical:
        return False

    try:
        shutil.copy2(snapshot.copy, snapshot.source)
    except OSError as ex:
        raise SessionError(
            f"Failed to restore unchanged {database_name} "
            f"'{snapshot.source}': {ex}"
        ) from ex

    return True


def reconcile_userdb(snapshot: DatabaseSnapshot) -> bool:
    """
    Reconcile userdb.sqlite and report tables containing genuine changes.

    Returns True if incidental SQLite-only churn was removed. If genuine
    logical changes exist, the live database is preserved and a table-level
    summary is displayed.
    """
    restored = reconcile_database(snapshot)

    if restored:
        return True

    try:
        tables = changed_tables(snapshot.copy, snapshot.source)
    except SQLiteCompareError as ex:
        raise SessionError(
            f"Failed to summarize userdb.sqlite changes: {ex}"
        ) from ex

    summary = (
        format_changed_tables(tables)
        if tables
        else "(schema change outside tables)"
    )
    prompts.show_summary(
        "userdb.sqlite logical changes:",
        summary,
    )

    return False


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

    status = git_manager.status()
    prompts.show_summary("Local changes detected:", status)

    options = [
        "Commit and push changes",
        "Stash changes",
        "Discard local changes",
        "Do nothing",
    ]

    choice = prompts.choose_action("Select a cleanup action:", options)
    action = list(CleanupAction)[choice]

    if action == CleanupAction.COMMIT:
        changed_paths = git_manager.changed_paths()
        selected_paths = prompts.choose_items(
            "Select changes to commit:",
            changed_paths,
        )

        if not selected_paths:
            return

        default_msg = generate_default_commit_message()
        commit_msg = prompts.request_commit_message(default_msg)

        git_manager.add_paths(selected_paths)
        git_manager.commit_paths(commit_msg, selected_paths)
        git_manager.push()

    elif action == CleanupAction.STASH:
        git_manager.stash()

    elif action == CleanupAction.DISCARD:
        tracked_paths = git_manager.tracked_changed_paths()
        selected_paths = prompts.choose_items(
            "Select tracked changes to discard:",
            tracked_paths,
        )

        if not selected_paths:
            return

        git_manager.restore_paths(selected_paths)

    elif action == CleanupAction.DO_NOTHING:
        pass
