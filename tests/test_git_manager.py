from pathlib import Path
import subprocess

import pytest

from kstars_sync.git_manager import GitManager, GitError


def git(cwd: Path, *args: str) -> str:
    """Run git and return stdout."""

    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )

    return result.stdout.strip()


def commit_file(repo: Path, filename: str, contents: str, message: str):
    path = repo / filename
    path.write_text(contents)

    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def initialise_repo(path: Path) -> str:
    """
    Create a usable repository.

    Returns the default branch name.
    """

    git(path, "init")
    git(path, "config", "user.name", "Unit Test")
    git(path, "config", "user.email", "unit@test")

    #
    # IMPORTANT:
    #
    # Git 2.43 leaves HEAD unborn until the first commit.
    # kstars-sync will never operate on such a repository,
    # so create an initial commit here.
    #
    commit_file(path, ".gitignore", "# test\n", "Initial commit")

    return git(path, "branch", "--show-current")


def test_current_branch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    branch = initialise_repo(repo)

    gm = GitManager(repo)

    assert gm.current_branch() == branch


def test_has_local_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    initialise_repo(repo)

    gm = GitManager(repo)

    assert not gm.has_local_changes()

    (repo / "one.txt").write_text("changed")

    assert gm.has_local_changes()


def test_add_all_and_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    initialise_repo(repo)

    gm = GitManager(repo)

    (repo / "one.txt").write_text("hello")

    gm.add_all()
    gm.commit("Second commit")

    assert not gm.has_local_changes()


def test_restore(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    initialise_repo(repo)

    commit_file(repo, "one.txt", "one", "file")

    gm = GitManager(repo)

    (repo / "one.txt").write_text("modified")

    assert gm.has_local_changes()

    gm.restore()

    assert not gm.has_local_changes()

    assert (repo / "one.txt").read_text() == "one"


def test_validate_repository(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))

    repo = tmp_path / "repo"
    repo.mkdir()

    branch = initialise_repo(repo)

    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", branch)

    gm = GitManager(repo)

    gm.validate_repository()


def test_remote_ahead(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))

    repo1 = tmp_path / "repo1"
    repo1.mkdir()

    branch = initialise_repo(repo1)

    git(repo1, "remote", "add", "origin", str(remote))
    git(repo1, "push", "-u", "origin", branch)

    repo2 = tmp_path / "repo2"

    git(tmp_path, "clone", str(remote), str(repo2))

    git(repo2, "config", "user.name", "Unit Test")
    git(repo2, "config", "user.email", "unit@test")

    commit_file(repo2, "two.txt", "two", "Second commit")

    git(repo2, "push")

    gm = GitManager(repo1)

    gm.fetch()

    assert gm.remote_ahead_count() == 1
    assert "Second commit" in gm.remote_commit_summary()


def test_validate_repository_without_upstream(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    initialise_repo(repo)

    gm = GitManager(repo)

    with pytest.raises(GitError):
        gm.validate_repository()


def test_changed_paths_includes_tracked_and_untracked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    commit_file(repo, "tracked.txt", "original", "tracked file")

    (repo / "tracked.txt").write_text("modified")
    (repo / "untracked.txt").write_text("new")

    gm = GitManager(repo)

    assert gm.changed_paths() == [
        "tracked.txt",
        "untracked.txt",
    ]


def test_tracked_changed_paths_excludes_untracked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    commit_file(repo, "tracked.txt", "original", "tracked file")

    (repo / "tracked.txt").write_text("modified")
    (repo / "untracked.txt").write_text("new")

    gm = GitManager(repo)

    assert gm.tracked_changed_paths() == ["tracked.txt"]


def test_add_paths_stages_only_selected_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    commit_file(repo, "one.txt", "one", "one")
    commit_file(repo, "two.txt", "two", "two")

    (repo / "one.txt").write_text("changed one")
    (repo / "two.txt").write_text("changed two")

    gm = GitManager(repo)
    gm.add_paths(["one.txt"])

    assert git(repo, "diff", "--cached", "--name-only") == "one.txt"
    assert git(repo, "diff", "--name-only") == "two.txt"


def test_commit_paths_does_not_include_unselected_staged_change(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    commit_file(repo, "one.txt", "one", "one")
    commit_file(repo, "two.txt", "two", "two")

    (repo / "one.txt").write_text("changed one")
    (repo / "two.txt").write_text("changed two")

    git(repo, "add", "two.txt")

    gm = GitManager(repo)
    gm.add_paths(["one.txt"])
    gm.commit_paths("selective commit", ["one.txt"])

    committed = git(repo, "show", "--name-only", "--format=", "HEAD")
    assert committed == "one.txt"

    staged = git(repo, "diff", "--cached", "--name-only")
    assert staged == "two.txt"


def test_commit_paths_supports_selected_untracked_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    (repo / "new.txt").write_text("new")

    gm = GitManager(repo)
    gm.add_paths(["new.txt"])
    gm.commit_paths("add new file", ["new.txt"])

    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "new.txt"


def test_restore_paths_discards_only_selected_tracked_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    initialise_repo(repo)

    commit_file(repo, "one.txt", "one", "one")
    commit_file(repo, "two.txt", "two", "two")

    (repo / "one.txt").write_text("changed one")
    (repo / "two.txt").write_text("changed two")

    gm = GitManager(repo)
    gm.restore_paths(["one.txt"])

    assert (repo / "one.txt").read_text() == "one"
    assert (repo / "two.txt").read_text() == "changed two"
