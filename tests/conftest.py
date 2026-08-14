import subprocess

import pytest


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A real local git repo with one commit, branch forced to 'main'
    regardless of the local git install's default branch name."""
    root = tmp_path / "work"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "hello.txt").write_text("hi\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial commit")
    _git(root, "branch", "-M", "main")
    return root


@pytest.fixture
def bare_remote(tmp_path):
    """A local bare repo standing in for 'origin' -- real git push/fetch
    over a file:// URL, no network or GitHub credentials involved."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
    return remote
