from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from kstars_sync.config import Config, ConfigError, RuntimeValidationError
from kstars_sync.git_manager import GitError
from kstars_sync.process import CompletedApplication, ProcessError
from kstars_sync.session import SessionError
from kstars_sync.workflow import run_workflow


def make_config(
    repo=Path("/tmp/repo"),
    kstars=Path("/usr/bin/kstars"),
    continue_without_fetch=False,
    compare_userdb=True,
    dry_run=False,
    verbose=False,
) -> Config:
    return Config(
        repo=repo,
        kstars=kstars,
        continue_without_fetch=continue_without_fetch,
        compare_userdb=compare_userdb,
        dry_run=dry_run,
        verbose=verbose,
    )


@pytest.fixture(autouse=True)
def mock_database_snapshot():
    snapshot = MagicMock()

    with patch(
        "kstars_sync.workflow.session.preserve_userdb",
        return_value=snapshot,
    ) as preserve:
        yield preserve, snapshot


@pytest.fixture(autouse=True)
def mock_userdb_reconcile():
    with patch(
        "kstars_sync.workflow.session.reconcile_userdb",
        return_value=False,
    ) as reconcile:
        yield reconcile


@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_config_validation_failure(mock_val_cfg, mock_val_rt):
    mock_val_cfg.side_effect = ConfigError("Invalid repo")
    cfg = make_config()

    exit_code = run_workflow(cfg)
    assert exit_code == 1


@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_runtime_validation_failure(mock_val_cfg, mock_val_rt):
    mock_val_rt.side_effect = RuntimeValidationError("git not found")
    cfg = make_config()

    exit_code = run_workflow(cfg)
    assert exit_code == 1


@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_git_validation_failure(
    mock_val_cfg, mock_val_rt, mock_git_cls
):
    mock_gm = MagicMock()
    mock_gm.validate_repository.side_effect = GitError("No upstream")
    mock_git_cls.return_value = mock_gm

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 1


@patch("kstars_sync.workflow.process.is_running", return_value=True)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_already_running(
    mock_val_cfg, mock_val_rt, mock_git_cls, mock_is_running
):
    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 1


@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_dry_run(
    mock_val_cfg, mock_val_rt, mock_git_cls, mock_is_running
):
    cfg = make_config(dry_run=True)
    exit_code = run_workflow(cfg)

    assert exit_code == 0


@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=False)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_pre_launch_cancelled(
    mock_val_cfg, mock_val_rt, mock_git_cls, mock_is_running, mock_pre_sync
):
    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 1


@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_app_launch_failure(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
):
    mock_run_app.side_effect = ProcessError("Failed to start")
    cfg = make_config()

    exit_code = run_workflow(cfg)
    assert exit_code == 1


@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=False)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_nonzero_exit_cleanup_cancelled(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
):
    mock_run_app.return_value = CompletedApplication(returncode=42)
    cfg = make_config()

    exit_code = run_workflow(cfg)
    assert exit_code == 42


@patch("kstars_sync.workflow.session.post_launch_cleanup")
@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=True)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_success(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
    mock_cleanup,
):
    mock_run_app.return_value = CompletedApplication(returncode=0)
    cfg = make_config()

    exit_code = run_workflow(cfg)

    assert exit_code == 0
    mock_cleanup.assert_called_once()


@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_snapshot_failure_aborts_before_launch(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_database_snapshot,
):
    preserve, snapshot = mock_database_snapshot
    preserve.side_effect = SessionError("copy failed")

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 1
    preserve.assert_called_once_with(cfg.repo)
    mock_run_app.assert_not_called()
    snapshot.cleanup.assert_not_called()


@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_snapshot_cleaned_after_launch_failure(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_database_snapshot,
):
    preserve, snapshot = mock_database_snapshot
    mock_run_app.side_effect = ProcessError("Failed to start")

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 1
    preserve.assert_called_once_with(cfg.repo)
    snapshot.cleanup.assert_called_once()


@patch("kstars_sync.workflow.session.post_launch_cleanup")
@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=True)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_snapshot_cleaned_after_success(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
    mock_cleanup,
    mock_database_snapshot,
):
    preserve, snapshot = mock_database_snapshot
    mock_run_app.return_value = CompletedApplication(returncode=0)

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 0
    preserve.assert_called_once_with(cfg.repo)
    snapshot.cleanup.assert_called_once()


@patch("kstars_sync.workflow.session.post_launch_cleanup")
@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=True)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_reconciles_before_git_cleanup(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
    mock_cleanup,
    mock_database_snapshot,
    mock_userdb_reconcile,
):
    preserve, snapshot = mock_database_snapshot
    mock_run_app.return_value = CompletedApplication(returncode=0)

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 0
    mock_userdb_reconcile.assert_called_once_with(snapshot)
    mock_cleanup.assert_called_once()

    reconcile_order = mock_userdb_reconcile.call_args
    cleanup_order = mock_cleanup.call_args
    assert reconcile_order is not None
    assert cleanup_order is not None


@patch("kstars_sync.workflow.session.post_launch_cleanup")
@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=True)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_reconcile_failure_continues_to_git_cleanup(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
    mock_cleanup,
    mock_database_snapshot,
    mock_userdb_reconcile,
):
    preserve, snapshot = mock_database_snapshot
    mock_run_app.return_value = CompletedApplication(returncode=0)
    mock_userdb_reconcile.side_effect = SessionError("comparison failed")

    cfg = make_config()
    exit_code = run_workflow(cfg)

    assert exit_code == 0
    mock_userdb_reconcile.assert_called_once_with(snapshot)
    mock_cleanup.assert_called_once()
    snapshot.cleanup.assert_called_once()


@patch("kstars_sync.workflow.session.post_launch_cleanup")
@patch("kstars_sync.workflow.session.should_proceed_after_exit", return_value=True)
@patch("kstars_sync.workflow.process.run_application")
@patch("kstars_sync.workflow.session.pre_launch_sync", return_value=True)
@patch("kstars_sync.workflow.process.is_running", return_value=False)
@patch("kstars_sync.workflow.GitManager")
@patch("kstars_sync.workflow.validate_runtime")
@patch("kstars_sync.workflow.validate_config")
def test_workflow_compare_userdb_disabled_skips_snapshot_and_reconcile(
    mock_val_cfg,
    mock_val_rt,
    mock_git_cls,
    mock_is_running,
    mock_pre_sync,
    mock_run_app,
    mock_should_proceed,
    mock_cleanup,
    mock_database_snapshot,
    mock_userdb_reconcile,
):
    preserve, snapshot = mock_database_snapshot
    mock_run_app.return_value = CompletedApplication(returncode=0)

    cfg = make_config(compare_userdb=False)
    exit_code = run_workflow(cfg)

    assert exit_code == 0
    preserve.assert_not_called()
    mock_userdb_reconcile.assert_not_called()
    snapshot.cleanup.assert_not_called()
    mock_cleanup.assert_called_once()
