from datetime import datetime
from unittest.mock import MagicMock, patch

from kstars_sync.git_manager import GitError
from kstars_sync.session import (
    CleanupAction,
    generate_default_commit_message,
    post_launch_cleanup,
    pre_launch_sync,
    should_proceed_after_exit,
)


def test_generate_default_commit_message_custom():
    fixed_time = datetime(2026, 7, 30, 18, 30, 0)
    msg = generate_default_commit_message(
        hostname="observatory-pc",
        now=fixed_time,
    )

    assert msg == "observatory-pc 2026-07-30 18:30:00"


def test_generate_default_commit_message_default():
    msg = generate_default_commit_message()
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_pre_launch_sync_up_to_date():
    gm = MagicMock()
    gm.remote_ahead_count.return_value = 0

    assert pre_launch_sync(gm) is True
    gm.fetch.assert_called_once()
    gm.pull.assert_not_called()


def test_pre_launch_sync_fetch_fails_and_cancelled():
    gm = MagicMock()
    gm.fetch.side_effect = GitError("Network error")

    with patch("kstars_sync.prompts.confirm", return_value=False):
        assert pre_launch_sync(gm, continue_without_fetch=False) is False


def test_pre_launch_sync_fetch_fails_and_accepted():
    gm = MagicMock()
    gm.fetch.side_effect = GitError("Network error")
    gm.remote_ahead_count.return_value = 0

    with patch("kstars_sync.prompts.confirm", return_value=True):
        assert pre_launch_sync(gm, continue_without_fetch=False) is True


def test_pre_launch_sync_fetch_fails_continue_automatically():
    gm = MagicMock()
    gm.fetch.side_effect = GitError("Network error")
    gm.remote_ahead_count.return_value = 0

    assert pre_launch_sync(gm, continue_without_fetch=True) is True


def test_pre_launch_sync_pull_success():
    gm = MagicMock()
    gm.remote_ahead_count.return_value = 2
    gm.remote_commit_summary.return_value = "commit 1\ncommit 2"

    with patch("kstars_sync.prompts.confirm", return_value=True), patch(
        "kstars_sync.prompts.show_summary"
    ) as mock_summary:

        assert pre_launch_sync(gm) is True

    mock_summary.assert_called_once()
    gm.pull.assert_called_once()


def test_pre_launch_sync_pull_declined():
    gm = MagicMock()
    gm.remote_ahead_count.return_value = 1

    with patch("kstars_sync.prompts.confirm", return_value=False):
        assert pre_launch_sync(gm) is True

    gm.pull.assert_not_called()


def test_pre_launch_sync_pull_fails_and_cancelled():
    gm = MagicMock()
    gm.remote_ahead_count.return_value = 1
    gm.pull.side_effect = GitError("Merge conflict")

    # First confirm: attempt pull -> True
    # Second confirm: continue after pull failure -> False
    with patch("kstars_sync.prompts.confirm", side_effect=[True, False]):
        assert pre_launch_sync(gm) is False


def test_should_proceed_after_exit_success():
    assert should_proceed_after_exit(0) is True


def test_should_proceed_after_exit_nonzero_user_cancelled():
    with patch("kstars_sync.prompts.confirm", return_value=False):
        assert should_proceed_after_exit(1) is False


def test_should_proceed_after_exit_nonzero_user_accepted():
    with patch("kstars_sync.prompts.confirm", return_value=True):
        assert should_proceed_after_exit(1) is True


def test_post_launch_cleanup_no_changes():
    gm = MagicMock()
    gm.has_local_changes.return_value = False

    post_launch_cleanup(gm)

    gm.diff_summary.assert_not_called()


def test_post_launch_cleanup_commit():
    gm = MagicMock()
    gm.has_local_changes.return_value = True
    gm.diff_summary.return_value = "1 file changed"

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=0
    ), patch(
        "kstars_sync.prompts.request_commit_message",
        return_value="custom commit msg",
    ):

        post_launch_cleanup(gm)

    gm.add_all.assert_called_once()
    gm.commit.assert_called_once_with("custom commit msg")
    gm.push.assert_called_once()


def test_post_launch_cleanup_stash():
    gm = MagicMock()
    gm.has_local_changes.return_value = True

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=1
    ):

        post_launch_cleanup(gm)

    gm.stash.assert_called_once()


def test_post_launch_cleanup_discard():
    gm = MagicMock()
    gm.has_local_changes.return_value = True

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=2
    ):

        post_launch_cleanup(gm)

    gm.restore.assert_called_once()


def test_post_launch_cleanup_do_nothing():
    gm = MagicMock()
    gm.has_local_changes.return_value = True

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=3
    ):

        post_launch_cleanup(gm)

    gm.add_all.assert_not_called()
    gm.stash.assert_not_called()
    gm.restore.assert_not_called()