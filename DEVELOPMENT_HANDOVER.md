# KStars Sync -- Development Handover

## Project goal

Create a Python launcher for KStars that manages the KStars data
directory as a Git working copy.

Workflow:

1.  User runs the launcher (or a generated `.desktop` entry).
2.  Validate configuration and repository.
3.  Refuse to continue if KStars is already running.
4.  `git fetch`.
5.  If upstream has changes:
    -   show a summary,
    -   always ask whether to `git pull --ff-only`.
    -   if pull fails, ask whether to continue launching anyway.
6.  Launch KStars and wait for it to exit.
7.  If KStars exits non-zero, ask whether to continue to Git cleanup.
8.  If there are local changes:
    -   show a diff summary,
    -   offer:
        -   Commit (using `git add -A`, editable default commit message
            of timestamp + hostname, then push)
        -   Stash
        -   Discard (`git restore .`)
        -   Do nothing
9.  Push only after a successful commit.
10. Exit.

## Design decisions

-   Language: Python 3.12
-   UI: terminal only (no kdialog)
-   Git executed via the git executable (no GitPython)
-   Repository defaults to the directory containing the launcher,
    override via CLI.
-   KStars defaults to `/usr/bin/kstars`, override via CLI.
-   Current branch only.
-   Upstream must already be configured.
-   Pull is always `git pull --ff-only`.
-   Add is always `git add -A`.
-   Discard is `git restore .`.
-   Generate a `.desktop` launcher.
-   Prevent running if KStars is already running.

## Current project structure

    kstars_sync/
        __init__.py
        config.py
        git_manager.py
        process.py
        prompts.py

    tests/
        test_config.py
        test_git_manager.py
        test_process.py
        test_prompts.py

## Current status

All current tests pass:

    22 passed

The completed modules should be treated as stable unless bugs are found.

## Remaining modules

Implement:

-   `kstars_sync/session.py`
-   `tests/test_session.py`
-   `kstars_sync/workflow.py`
-   `tests/test_workflow.py`
-   `kstars_sync/main.py`
-   desktop file generation
-   README

## Architectural intent

-   `config.py` owns configuration.
-   `git_manager.py` owns every Git command.
-   `process.py` owns process inspection and application launch.
-   `prompts.py` owns all terminal interaction.
-   `session.py` owns Git workflow decisions.
-   `workflow.py` orchestrates the application.
-   `main.py` is only the CLI entry point.

No module should duplicate another module's responsibility.

## Testing

Run:

``` bash
python -m pytest --verbose
```

Keep all existing tests passing while adding the remaining
functionality.
