from unittest.mock import patch

from kstars_sync.prompts import (
    choose_action,
    choose_items,
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


def test_choose_items_all():
    with patch("builtins.input", return_value="a"):
        assert choose_items(
            "Select",
            ["one", "two", "three"],
        ) == ["one", "two", "three"]


def test_choose_items_none_blank():
    with patch("builtins.input", return_value=""):
        assert choose_items(
            "Select",
            ["one", "two"],
        ) == []


def test_choose_items_specific_numbers():
    with patch("builtins.input", return_value="1,3"):
        assert choose_items(
            "Select",
            ["one", "two", "three"],
        ) == ["one", "three"]


def test_choose_items_reprompts_after_invalid_selection():
    with patch("builtins.input", side_effect=["4", "2"]):
        assert choose_items(
            "Select",
            ["one", "two"],
        ) == ["two"]


def test_choose_items_rejects_duplicate_numbers():
    with patch("builtins.input", side_effect=["1,1", "1"]):
        assert choose_items(
            "Select",
            ["one", "two"],
        ) == ["one"]
