"""
git_manager.py

Wrapper around the Git executable.

This module is the only place in the application that should execute Git
commands. All Git-specific behaviour is encapsulated here.
"""

from __future__ import annotations

import os
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


def _run(
    args: list[str],
    repo_path: Path,
    capture_output: bool = True,
    timeout: int = 15,
    check: bool = True,
) -> GitResult:
    """Execute a git command safely inside PyInstaller bundles and standard runtimes."""
    env = os.environ.copy()

    # PyInstaller library cleanup to avoid subprocess library pollution
    for var in ["LD_LIBRARY_PATH", "LIBPATH", "PYTHONPATH"]:
        orig_var = f"{var}_ORIG"
        if orig_var in env:
            env[var] = env[orig_var]
        else:
            env.pop(var, None)

    # Prevent interactive credential prompts
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"

    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=capture_output,
            text=True,
            check=check,
            timeout=timeout,
            env=env,
        )
        return GitResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired as err:
        raise GitError(
            f"Git operation 'git {' '.join(args)}' timed out after {timeout} seconds."
        ) from err
    except subprocess.CalledProcessError as err:
        raise GitError(
            f"Git operation failed: {err.stderr.strip() if err.stderr else str(err)}"
        ) from err


class GitManager:
    """Interface to a Git repository."""

    def __init__(self, repo: Path | str, verbose: bool = False):
        self.repo = Path(repo)
        self.verbose = verbose

    def _run(self, *args: str, check: bool = True) -> GitResult:
        """Internal helper forwarding to module-level _run."""
        return _run(list(args), self.repo, check=check)

    # ------------------------------------------------------------------
    # Repository validation
    # ------------------------------------------------------------------

    def validate_repository(self) -> None:
        """
        Validate assumptions required by kstars-sync.
        """
        self._run("rev-parse", "--is-inside-work-tree")

        if not self.has_upstream():
            raise GitError("The current branch has no upstream configured.")

    # ------------------------------------------------------------------
    # Repository information
    # ------------------------------------------------------------------

    def current_branch(self) -> str:
        """Return the current branch."""
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def has_upstream(self) -> bool:
        """Return True if the current branch has an upstream."""
        result = self._run("rev-parse", "--abbrev-ref", "@{u}", check=False)
        return result.returncode == 0

    # ------------------------------------------------------------------
    # Synchronisation
    # ------------------------------------------------------------------

    def fetch(self) -> None:
        """Fetch from the configured remote."""
        self._run("fetch")

    def pull(self) -> None:
        """Perform a fast-forward pull."""
        self._run("pull", "--ff-only")

    def remote_ahead_count(self) -> int:
        """Return the number of commits available upstream."""
        result = self._run("rev-list", "--count", "HEAD..@{u}")
        return int(result.stdout.strip())

    def remote_commit_summary(self) -> str:
        """Return one-line summaries of upstream commits."""
        result = self._run("log", "--oneline", "HEAD..@{u}")
        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Working tree
    # ------------------------------------------------------------------

    def has_local_changes(self) -> bool:
        """Return True if the working tree contains modifications."""
        result = self._run("status", "--porcelain=v1")
        return bool(result.stdout.strip())

    def status(self) -> str:
        """Return git status in porcelain format."""
        result = self._run("status", "--porcelain=v1")
        return result.stdout.rstrip()

    def diff_summary(self) -> str:
        """Return a diffstat summary."""
        result = self._run("diff", "--stat")
        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def add_all(self) -> None:
        """Stage all changes."""
        self._run("add", "-A")

    def commit(self, message: str) -> None:
        """Create a commit."""
        self._run("commit", "-m", message)

    def push(self) -> None:
        """Push to the configured upstream."""
        self._run("push")

    # ------------------------------------------------------------------
    # Stash
    # ------------------------------------------------------------------

    def stash(self) -> None:
        """Create a stash."""
        self._run("stash", "push")

    def stash_pop(self) -> None:
        """Restore the most recent stash."""
        self._run("stash", "pop")

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore(self) -> None:
        """Discard tracked modifications."""
        self._run("restore", ".")