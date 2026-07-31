"""
git_manager.py

Wrapper around the Git executable.

This module is the only place in the application that should execute Git
commands. All Git-specific behaviour is encapsulated here.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """Raised when a Git operation fails."""


@dataclass(slots=True)
class GitResult:
    """Result of a Git command."""

    stdout: str
    stderr: str
    returncode: int


class GitManager:
    """Interface to a Git repository."""

    def __init__(self, repo: Path, verbose: bool = False):
        self.repo = Path(repo)
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _run(self, *args: str, check: bool =True) -> GitResult:
        """
        Execute a Git command.

        Parameters
        ----------
        *args
            Arguments passed to git.

        check
            Raise GitError on non-zero exit status.

        Returns
        -------
        GitResult
        """

        command = ["git", *args]

        if self.verbose:
            print("$", " ".join(command))

        result = subprocess.run(
            command,
            cwd=self.repo,
            text=True,
            capture_output=True,
        )

        git_result = GitResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed\n\n"
                f"{result.stderr.strip()}"
            )

        return git_result

    # ------------------------------------------------------------------
    # Repository validation
    # ------------------------------------------------------------------

    def validate_repository(self) -> None:
        """
        Validate assumptions required by kstars-sync.

        Checks:

        * repository is inside a working tree
        * current branch has an upstream
        """

        self._run(
            "rev-parse",
            "--is-inside-work-tree",
        )

        if not self.has_upstream():
            raise GitError(
                "The current branch has no upstream configured."
            )

    # ------------------------------------------------------------------
    # Repository information
    # ------------------------------------------------------------------

    def current_branch(self) -> str:
        """Return the current branch."""

        result = self._run(
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        )

        return result.stdout.strip()

    def has_upstream(self) -> bool:
        """Return True if the current branch has an upstream."""

        result = self._run(
            "rev-parse",
            "--abbrev-ref",
            "@{u}",
            check=False,
        )

        return result.returncode == 0

    # ------------------------------------------------------------------
    # Synchronisation
    # ------------------------------------------------------------------

    def fetch(self) -> None:
        """Fetch from the configured remote."""

        self._run("fetch")

    def pull(self) -> None:
        """Perform a fast-forward pull."""

        self._run(
            "pull",
            "--ff-only",
        )

    def remote_ahead_count(self) -> int:
        """
        Return the number of commits available upstream.
        """

        result = self._run(
            "rev-list",
            "--count",
            "HEAD..@{u}",
        )

        return int(result.stdout.strip())

    def remote_commit_summary(self) -> str:
        """
        Return one-line summaries of upstream commits.
        """

        result = self._run(
            "log",
            "--oneline",
            "HEAD..@{u}",
        )

        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Working tree
    # ------------------------------------------------------------------

    def has_local_changes(self) -> bool:
        """Return True if the working tree contains modifications."""

        result = self._run(
            "status",
            "--porcelain=v1",
        )

        return bool(result.stdout.strip())

    def status(self) -> str:
        """
        Return git status in porcelain format.
        """

        result = self._run(
            "status",
            "--porcelain=v1",
        )

        return result.stdout.rstrip()

    def diff_summary(self) -> str:
        """
        Return a diffstat summary.
        """

        result = self._run(
            "diff",
            "--stat",
        )

        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def add_all(self) -> None:
        """Stage all changes."""

        self._run(
            "add",
            "-A",
        )

    def commit(self, message: str) -> None:
        """Create a commit."""

        self._run(
            "commit",
            "-m",
            message,
        )

    def push(self) -> None:
        """Push to the configured upstream."""

        self._run("push")

    # ------------------------------------------------------------------
    # Stash
    # ------------------------------------------------------------------

    def stash(self) -> None:
        """Create a stash."""

        self._run(
            "stash",
            "push",
        )

    def stash_pop(self) -> None:
        """Restore the most recent stash."""

        self._run(
            "stash",
            "pop",
        )

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore(self) -> None:
        """Discard tracked modifications."""

        self._run(
            "restore",
            ".",
        )

