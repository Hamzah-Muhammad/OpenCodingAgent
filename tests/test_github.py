import subprocess

import pytest

from open_coding_agent.tools import git, github
from open_coding_agent.tools.fs import ToolError


def test_refuses_on_main(repo, bare_remote):
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)

    assert "REFUSED" in github.preview_pr_create(str(repo), "title")
    with pytest.raises(ToolError):
        github.pr_create(str(repo), "title")


def test_refuses_when_branch_not_pushed_yet(repo, bare_remote):
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)
    git.git_checkout_branch(str(repo), "feature/x")  # created locally, never pushed

    preview = github.preview_pr_create(str(repo), "title")
    assert "REFUSED" in preview
    assert "git_push" in preview
    with pytest.raises(ToolError):
        github.pr_create(str(repo), "title")


def test_calls_gh_with_expected_args_once_pushed(repo, bare_remote, monkeypatch):
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)
    git.git_checkout_branch(str(repo), "feature/x")
    git.git_push(str(repo))  # real push to the local bare remote

    captured = {}

    def fake_run_gh(root, args):
        captured["root"] = root
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="https://example.com/pr/1\n", stderr="")

    monkeypatch.setattr(github, "_run_gh", fake_run_gh)

    result = github.pr_create(str(repo), "My title", body="My body")

    assert "example.com/pr/1" in result
    assert captured["args"] == [
        "pr",
        "create",
        "--title",
        "My title",
        "--body",
        "My body",
        "--head",
        "feature/x",
        "--base",
        "main",
    ]


def test_reports_gh_failure_without_raising(repo, bare_remote, monkeypatch):
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True)
    git.git_checkout_branch(str(repo), "feature/x")
    git.git_push(str(repo))

    monkeypatch.setattr(
        github,
        "_run_gh",
        lambda root, args: subprocess.CompletedProcess(
            args, 1, stdout="", stderr="not authenticated"
        ),
    )

    result = github.pr_create(str(repo), "title")
    assert "failed" in result.lower()
    assert "not authenticated" in result
