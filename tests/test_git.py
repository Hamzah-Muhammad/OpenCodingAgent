import subprocess

import pytest

from open_coding_agent.tools import git
from open_coding_agent.tools.errors import ToolError


def test_git_status_clean(repo):
    assert git.git_status(str(repo)) == "(clean working tree)"


def test_git_status_dirty(repo):
    (repo / "new.txt").write_text("x")
    assert "new.txt" in git.git_status(str(repo))


def test_git_diff_no_changes(repo):
    assert git.git_diff(str(repo)) == "(no changes)"


def test_git_diff_shows_changes(repo):
    (repo / "hello.txt").write_text("bye\n")
    assert "-hi" in git.git_diff(str(repo))


def test_git_commit_stages_and_commits(repo):
    (repo / "new.txt").write_text("x")
    result = git.git_commit(str(repo), "add new file")
    assert "add new file" in result
    assert git.git_status(str(repo)) == "(clean working tree)"


def test_git_commit_scoped_to_specific_paths(repo):
    (repo / "a.txt").write_text("a")
    (repo / "b.txt").write_text("b")
    git.git_commit(str(repo), "just a", paths=["a.txt"])
    assert "b.txt" in git.git_status(str(repo))  # b.txt still untracked


def test_git_checkout_branch_creates_and_switches(repo):
    git.git_checkout_branch(str(repo), "feature/x")
    assert git._current_branch(str(repo)) == "feature/x"


class TestPushGuardrails:
    def test_refuses_on_main(self, repo, bare_remote):
        subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)

        assert "REFUSED" in git.preview_git_push(str(repo))
        with pytest.raises(ToolError):
            git.git_push(str(repo))

    def test_pushes_for_real_off_main(self, repo, bare_remote):
        subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)
        git.git_checkout_branch(str(repo), "feature/z")

        result = git.git_push(str(repo))

        assert "failed" not in result.lower()
        ls_remote = subprocess.run(
            ["git", "ls-remote", "--heads", str(bare_remote)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feature/z" in ls_remote.stdout

    def test_refuses_with_no_origin_at_all(self, repo):
        with pytest.raises(ToolError):
            git.git_push(str(repo))
