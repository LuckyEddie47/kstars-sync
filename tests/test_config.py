from pathlib import Path

import pytest

from kstars_sync.config import (
    Config,
    ConfigError,
    load_config,
    validate_config,
)


def create_git_repo(path: Path) -> None:
    """Create a minimal Git repository."""

    (path / ".git").mkdir()


def test_valid_configuration(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    kstars = tmp_path / "kstars"
    kstars.write_text("#!/bin/sh\n")
    kstars.chmod(0o755)

    cfg = Config(
        repo=repo,
        kstars=kstars,
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    validate_config(cfg)


def test_missing_repository(tmp_path):
    cfg = Config(
        repo=tmp_path / "missing",
        kstars=tmp_path / "kstars",
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    with pytest.raises(ConfigError, match="Repository does not exist"):
        validate_config(cfg)


def test_repository_not_directory(tmp_path):
    repo = tmp_path / "repo"
    repo.write_text("")

    kstars = tmp_path / "kstars"
    kstars.write_text("")
    kstars.chmod(0o755)

    cfg = Config(
        repo=repo,
        kstars=kstars,
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    with pytest.raises(ConfigError, match="not a directory"):
        validate_config(cfg)


def test_not_git_repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    kstars = tmp_path / "kstars"
    kstars.write_text("")
    kstars.chmod(0o755)

    cfg = Config(
        repo=repo,
        kstars=kstars,
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    with pytest.raises(ConfigError, match="not a Git repository"):
        validate_config(cfg)


def test_missing_kstars(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    cfg = Config(
        repo=repo,
        kstars=tmp_path / "missing",
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    with pytest.raises(ConfigError, match="KStars executable not found"):
        validate_config(cfg)


def test_kstars_not_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    kstars = tmp_path / "kstars"
    kstars.mkdir()

    cfg = Config(
        repo=repo,
        kstars=kstars,
        continue_without_fetch=False,
        compare_userdb=True,
        dry_run=False,
        verbose=False,
    )

    with pytest.raises(ConfigError, match="not a file"):
        validate_config(cfg)


def test_compare_userdb_defaults_true(tmp_path):
    config_file = tmp_path / "missing.ini"

    cfg = load_config(["--config", str(config_file)])

    assert cfg.compare_userdb is True


def test_compare_userdb_can_be_disabled_in_config(tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        """
[sqlite]
compare_userdb=false
"""
    )

    cfg = load_config(["--config", str(config_file)])

    assert cfg.compare_userdb is False


def test_compare_userdb_can_be_enabled_in_config(tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        """
[sqlite]
compare_userdb=true
"""
    )

    cfg = load_config(["--config", str(config_file)])

    assert cfg.compare_userdb is True
