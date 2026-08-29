import subprocess

import pytest

from open_coding_agent.tools.fs import ALLOWED_ROOT_NAME


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def tmp_path(tmp_path):
    """Every temp working root is named after the sandbox.

    The agent refuses to operate in any directory whose final component is not
    ALLOWED_ROOT_NAME, so a test root called "work" or a bare tmp_path is
    rejected before the behaviour under test is ever reached. Renaming here
    keeps the tests exercising the real code path instead of forcing each one
    to know about the lock.
    """
    sandbox = tmp_path / ALLOWED_ROOT_NAME
    sandbox.mkdir(exist_ok=True)
    return sandbox


@pytest.fixture
def repo(tmp_path):
    """A real local git repo with one commit, branch forced to 'main'
    regardless of the local git install's default branch name."""
    root = tmp_path

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
