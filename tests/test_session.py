from datetime import datetime
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from kstars_sync.git_manager import GitError
from kstars_sync.sqlite_compare import SQLiteCompareError
from kstars_sync.session import (
    CleanupAction,
    SessionError,
    generate_default_commit_message,
    post_launch_cleanup,
    preserve_database,
    preserve_userdb,
    reconcile_database,
    reconcile_userdb,
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

    gm.status.assert_not_called()


def test_post_launch_cleanup_commit():
    gm = MagicMock()
    gm.has_local_changes.return_value = True
    gm.status.return_value = " M one.txt\n?? two.txt"
    gm.changed_paths.return_value = ["one.txt", "two.txt"]

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=0
    ), patch(
        "kstars_sync.prompts.choose_items",
        return_value=["one.txt"],
    ), patch(
        "kstars_sync.prompts.request_commit_message",
        return_value="custom commit msg",
    ):

        post_launch_cleanup(gm)

    gm.add_paths.assert_called_once_with(["one.txt"])
    gm.commit_paths.assert_called_once_with(
        "custom commit msg",
        ["one.txt"],
    )
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
    gm.tracked_changed_paths.return_value = ["one.txt", "two.txt"]

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=2
    ), patch(
        "kstars_sync.prompts.choose_items",
        return_value=["two.txt"],
    ):

        post_launch_cleanup(gm)

    gm.restore_paths.assert_called_once_with(["two.txt"])


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


def test_preserve_userdb_creates_copy(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    source = repo / "userdb.sqlite"
    source.write_bytes(b"database contents")

    snapshot = preserve_userdb(repo)

    try:
        assert snapshot.source == source
        assert snapshot.copy.exists()
        assert snapshot.copy.read_bytes() == source.read_bytes()
        assert snapshot.copy != source
    finally:
        snapshot.cleanup()


def test_preserve_userdb_cleanup_removes_temporary_copy(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "userdb.sqlite").write_bytes(b"database contents")

    snapshot = preserve_userdb(repo)
    copy = snapshot.copy
    temporary_directory = copy.parent

    assert copy.exists()
    assert temporary_directory.exists()

    snapshot.cleanup()

    assert not copy.exists()
    assert not temporary_directory.exists()


def test_preserve_userdb_missing_database_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(SessionError, match="does not exist"):
        preserve_userdb(repo)


def test_preserve_userdb_directory_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "userdb.sqlite").mkdir()

    with pytest.raises(SessionError, match="not a file"):
        preserve_userdb(repo)


def test_preserve_userdb_copy_failure_raises(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "userdb.sqlite").write_bytes(b"database contents")

    temporary_directory = tmp_path / "temporary"
    cleanup_called = []

    class FakeTemporaryDirectory:
        def __init__(self, prefix):
            temporary_directory.mkdir()
            self.name = str(temporary_directory)

        def cleanup(self):
            cleanup_called.append(True)
            if temporary_directory.exists():
                temporary_directory.rmdir()

    monkeypatch.setattr(
        "kstars_sync.session.tempfile.TemporaryDirectory",
        FakeTemporaryDirectory,
    )

    def fail_copy(*args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr("kstars_sync.session.shutil.copy2", fail_copy)

    with pytest.raises(SessionError, match="Failed to preserve"):
        preserve_userdb(repo)

    assert cleanup_called == [True]
    assert not temporary_directory.exists()


def test_reconcile_userdb_restores_logically_identical_database(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"after")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    compare = MagicMock(return_value=True)
    monkeypatch.setattr(
        "kstars_sync.session.logically_identical",
        compare,
    )

    restored = reconcile_userdb(snapshot)

    assert restored is True
    compare.assert_called_once_with(preserved, source)
    assert source.read_bytes() == b"before"


def test_reconcile_userdb_leaves_logically_changed_database(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"genuine change")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    compare = MagicMock(return_value=False)
    monkeypatch.setattr(
        "kstars_sync.session.logically_identical",
        compare,
    )
    monkeypatch.setattr(
        "kstars_sync.session.changed_tables",
        MagicMock(return_value=["equipment"]),
    )
    monkeypatch.setattr(
        "kstars_sync.session.prompts.show_summary",
        MagicMock(),
    )

    restored = reconcile_userdb(snapshot)

    assert restored is False
    compare.assert_called_once_with(preserved, source)
    assert source.read_bytes() == b"genuine change"


def test_reconcile_userdb_comparison_failure_preserves_live_database(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"live database")
    preserved.write_bytes(b"preserved database")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    def fail_compare(*args, **kwargs):
        raise SQLiteCompareError("comparison failed")

    monkeypatch.setattr(
        "kstars_sync.session.logically_identical",
        fail_compare,
    )

    with pytest.raises(SessionError, match="Failed to compare"):
        reconcile_userdb(snapshot)

    assert source.read_bytes() == b"live database"


def test_reconcile_userdb_restore_failure_raises(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"after")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    monkeypatch.setattr(
        "kstars_sync.session.logically_identical",
        lambda *args: True,
    )

    def fail_copy(*args, **kwargs):
        raise OSError("restore failed")

    monkeypatch.setattr(
        "kstars_sync.session.shutil.copy2",
        fail_copy,
    )

    with pytest.raises(SessionError, match="Failed to restore"):
        reconcile_userdb(snapshot)

    assert source.read_bytes() == b"after"


def test_preserve_database_supports_other_database_filename(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    source = repo / "other.sqlite"
    source.write_bytes(b"database contents")

    snapshot = preserve_database(repo, "other.sqlite")

    try:
        assert snapshot.source == source
        assert snapshot.copy.name == "other.sqlite"
        assert snapshot.copy.read_bytes() == source.read_bytes()
    finally:
        snapshot.cleanup()


@pytest.mark.parametrize(
    "filename",
    [
        "../userdb.sqlite",
        "subdir/userdb.sqlite",
        "/tmp/userdb.sqlite",
    ],
)
def test_preserve_database_rejects_non_simple_filename(tmp_path, filename):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(SessionError, match="single relative filename"):
        preserve_database(repo, filename)


def test_preserve_userdb_delegates_to_generic_preserve(tmp_path, monkeypatch):
    expected = MagicMock()
    preserve = MagicMock(return_value=expected)

    monkeypatch.setattr(
        "kstars_sync.session.preserve_database",
        preserve,
    )

    result = preserve_userdb(tmp_path)

    assert result is expected
    preserve.assert_called_once_with(tmp_path, "userdb.sqlite")


def test_reconcile_database_supports_other_database_filename(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "other.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"after")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    compare = MagicMock(return_value=True)
    monkeypatch.setattr(
        "kstars_sync.session.logically_identical",
        compare,
    )

    restored = reconcile_database(snapshot)

    assert restored is True
    compare.assert_called_once_with(preserved, source)
    assert source.read_bytes() == b"before"


def test_reconcile_userdb_delegates_to_generic_reconcile(monkeypatch):
    snapshot = MagicMock()
    reconcile = MagicMock(return_value=True)

    monkeypatch.setattr(
        "kstars_sync.session.reconcile_database",
        reconcile,
    )

    result = reconcile_userdb(snapshot)

    assert result is True
    reconcile.assert_called_once_with(snapshot)


def test_reconcile_userdb_reports_changed_tables(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"after")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    monkeypatch.setattr(
        "kstars_sync.session.reconcile_database",
        lambda snapshot: False,
    )
    tables = MagicMock(return_value=["imageOverlays", "opticaltrains"])
    monkeypatch.setattr(
        "kstars_sync.session.changed_tables",
        tables,
    )
    summary = MagicMock()
    monkeypatch.setattr(
        "kstars_sync.session.prompts.show_summary",
        summary,
    )

    restored = reconcile_userdb(snapshot)

    assert restored is False
    tables.assert_called_once_with(preserved, source)
    summary.assert_called_once_with(
        "userdb.sqlite logical changes:",
        "Image overlays (imageOverlays)\n"
        "Optical trains (opticaltrains)",
    )


def test_reconcile_userdb_restored_database_has_no_change_report(
    tmp_path,
    monkeypatch,
):
    snapshot = MagicMock()

    monkeypatch.setattr(
        "kstars_sync.session.reconcile_database",
        lambda snapshot: True,
    )
    tables = MagicMock()
    monkeypatch.setattr(
        "kstars_sync.session.changed_tables",
        tables,
    )
    summary = MagicMock()
    monkeypatch.setattr(
        "kstars_sync.session.prompts.show_summary",
        summary,
    )

    restored = reconcile_userdb(snapshot)

    assert restored is True
    tables.assert_not_called()
    summary.assert_not_called()


def test_reconcile_userdb_summary_failure_raises(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "userdb.sqlite"
    preserved = tmp_path / "preserved.sqlite"

    source.write_bytes(b"after")
    preserved.write_bytes(b"before")

    snapshot = MagicMock()
    snapshot.source = source
    snapshot.copy = preserved

    monkeypatch.setattr(
        "kstars_sync.session.reconcile_database",
        lambda snapshot: False,
    )

    def fail_summary(*args, **kwargs):
        raise SQLiteCompareError("summary failed")

    monkeypatch.setattr(
        "kstars_sync.session.changed_tables",
        fail_summary,
    )

    with pytest.raises(SessionError, match="Failed to summarize"):
        reconcile_userdb(snapshot)

    assert source.read_bytes() == b"after"


def test_post_launch_cleanup_commit_no_selection_does_nothing():
    gm = MagicMock()
    gm.has_local_changes.return_value = True
    gm.changed_paths.return_value = ["one.txt"]

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=0
    ), patch(
        "kstars_sync.prompts.choose_items",
        return_value=[],
    ):

        post_launch_cleanup(gm)

    gm.add_paths.assert_not_called()
    gm.commit_paths.assert_not_called()
    gm.push.assert_not_called()


def test_post_launch_cleanup_discard_no_selection_does_nothing():
    gm = MagicMock()
    gm.has_local_changes.return_value = True
    gm.tracked_changed_paths.return_value = ["one.txt"]

    with patch("kstars_sync.prompts.show_summary"), patch(
        "kstars_sync.prompts.choose_action", return_value=2
    ), patch(
        "kstars_sync.prompts.choose_items",
        return_value=[],
    ):

        post_launch_cleanup(gm)

    gm.restore_paths.assert_not_called()


def test_post_launch_cleanup_shows_git_status():
    gm = MagicMock()
    gm.has_local_changes.return_value = True
    gm.status.return_value = " M one.txt\n?? new.txt"

    with patch(
        "kstars_sync.prompts.show_summary"
    ) as show_summary, patch(
        "kstars_sync.prompts.choose_action",
        return_value=3,
    ):
        post_launch_cleanup(gm)

    gm.status.assert_called_once()
    show_summary.assert_called_once_with(
        "Local changes detected:",
        " M one.txt\n?? new.txt",
    )
