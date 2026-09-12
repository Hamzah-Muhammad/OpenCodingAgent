"""GitHub-level operations, layered on top of local git (tools/git.py). Shells
out to the `gh` CLI rather than calling GitHub's REST API directly -- so
OpenCodingAgent never holds a credential itself, it delegates to tooling
that's already authenticated on the machine (`gh auth login`), keeping its
own tool surface a thin, parameter-limited wrapper instead of an API client
with a token to manage.
"""

import subprocess

from open_coding_agent.tools.errors import ToolError
from open_coding_agent.tools.fs import assert_allowed_root
from open_coding_agent.tools.git import _PROTECTED_BRANCHES, _current_branch, _run_git


def _run_gh(root: str, args: list[str]) -> subprocess.CompletedProcess:
    assert_allowed_root(root)
    try:
        return subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as e:
        raise ToolError("gh (GitHub CLI) is not installed or not on PATH") from e


def _pr_precheck(root: str) -> str | None:
    """Returns a refusal message if a PR can't be opened right now, else None.
    Shared by the preview and the executor so they never disagree."""
    branch = _current_branch(root)
    if branch in _PROTECTED_BRANCHES:
        return f"REFUSED: current branch is '{branch}' -- nothing to open a PR from."

    remote_check = _run_git(root, ["ls-remote", "--heads", "origin", branch])
    if remote_check.returncode != 0 or not remote_check.stdout.strip():
        return f"REFUSED: branch '{branch}' isn't pushed to origin yet -- run git_push first."
    return None


def preview_pr_create(root: str, title: str, body: str = "") -> str:
    refusal = _pr_precheck(root)
    if refusal:
        return refusal
    branch = _current_branch(root)
    return f"Open a PR: '{branch}' -> main\nTitle: {title}\n\n{body or '(no description)'}"


def pr_create(root: str, title: str, body: str = "") -> str:
    refusal = _pr_precheck(root)
    if refusal:
        raise ToolError(refusal)

    branch = _current_branch(root)
    result = _run_gh(
        root, ["pr", "create", "--title", title, "--body", body, "--head", branch, "--base", "main"]
    )
    if result.returncode != 0:
        return f"gh pr create failed (exit {result.returncode}): {result.stderr.strip()}"
    return result.stdout.strip() or "PR created."
