from unittest.mock import patch

from kstars_sync.prompts import (
    choose_action,
    confirm,
    request_commit_message,
)


def test_confirm_yes():
    with patch("builtins.input", return_value="y"):
        assert confirm("Continue?") is True


def test_confirm_no():
    with patch("builtins.input", return_value="n"):
        assert confirm("Continue?") is False


def test_confirm_default():
    with patch("builtins.input", return_value=""):
        assert confirm("Continue?", default=True) is True


def test_choose_action():
    with patch("builtins.input", return_value="2"):
        assert choose_action(
            "Select",
            ["one", "two"],
        ) == 1


def test_commit_message_override():
    with patch("builtins.input", return_value="new message"):
        assert request_commit_message(
            "default"
        ) == "new message"


def test_commit_message_default():
    with patch("builtins.input", return_value=""):
        assert request_commit_message(
            "default"
        ) == "default"
