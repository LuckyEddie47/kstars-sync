"""
prompts.py

Console user interaction helpers for kstars-sync.

This module contains all terminal prompting and display logic.
"""

from __future__ import annotations


def confirm(
    message: str,
    default: bool | None = None,
) -> bool:
    """
    Ask a yes/no question.

    Parameters
    ----------
    message
        Question to display.

    default
        Default response if the user presses Enter.
        None means no default.

    Returns
    -------
    bool
    """

    if default is True:
        suffix = " [Y/n]: "
    elif default is False:
        suffix = " [y/N]: "
    else:
        suffix = " [y/n]: "

    while True:
        answer = input(
            message + suffix
        ).strip().lower()

        if not answer and default is not None:
            return default

        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        print("Please answer yes or no.")


def choose_action(
    message: str,
    options: list[str],
) -> int:
    """
    Present numbered choices.

    Returns the zero-based index selected.
    """

    print(message)

    for index, option in enumerate(options, start=1):
        print(f"{index}) {option}")

    while True:
        answer = input("Choice: ").strip()

        try:
            choice = int(answer)

        except ValueError:
            print("Enter a number.")
            continue

        if 1 <= choice <= len(options):
            return choice - 1

        print("Invalid choice.")


def choose_items(
    message: str,
    options: list[str],
) -> list[str]:
    """
    Select zero or more items from a numbered list.

    Input accepts:
    - ``a`` or ``all`` for every item;
    - ``n``, ``none``, or a blank line for no items;
    - comma-separated item numbers such as ``1,3,4``.
    """

    print(message)

    for index, option in enumerate(options, start=1):
        print(f"{index}) {option}")

    while True:
        answer = input(
            "Select numbers separated by commas "
            "[a=all, n=none]: "
        ).strip().lower()

        if answer in ("", "n", "none"):
            return []

        if answer in ("a", "all"):
            return list(options)

        parts = [part.strip() for part in answer.split(",")]

        try:
            indices = [int(part) for part in parts]
        except ValueError:
            print("Enter comma-separated numbers, 'a', or 'n'.")
            continue

        if (
            not indices
            or any(index < 1 or index > len(options) for index in indices)
        ):
            print("Invalid selection.")
            continue

        if len(set(indices)) != len(indices):
            print("Do not select the same item more than once.")
            continue

        return [options[index - 1] for index in indices]


def show_summary(
    title: str,
    summary: str,
) -> None:
    """
    Display a summary block.
    """

    print()
    print(title)
    print("-" * len(title))

    if summary:
        print(summary)
    else:
        print("(no changes)")


def request_commit_message(
    default: str,
) -> str:
    """
    Ask for a commit message.

    The default is shown and may be edited.
    """

    message = input(
        f"Commit message [{default}]: "
    ).strip()

    if message:
        return message

    return default
