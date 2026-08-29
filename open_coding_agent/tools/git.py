import subprocess

from open_coding_agent.tools.fs import ToolError, assert_allowed_root

# OpenCodingAgent never pushes directly to these -- hard-coded, not
# user-configurable from a tool call. Push to a feature branch and open a
# PR by hand instead.
_PROTECTED_BRANCHES = {"main", "master"}


def _run_git(root: str, args: list[str]) -> subprocess.CompletedProcess:
    assert_allowed_root(root)
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as e:
        raise ToolError("git is not installed or not on PATH") from e


def _current_branch(root: str) -> str:
    result = _run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        raise ToolError(f"Couldn't determine current branch: {result.stderr.strip()}")
    return result.stdout.strip()


def git_status(root: str) -> str:
    result = _run_git(root, ["status", "--porcelain"])
    return result.stdout.strip() or "(clean working tree)"


def git_diff(root: str, path: str = None) -> str:
    args = ["diff"]
    if path:
        args.append(path)
    result = _run_git(root, args)
    return result.stdout.strip() or "(no changes)"


def preview_git_commit(root: str, message: str, paths: list[str] = None) -> str:
    diff_args = ["diff", "--cached"] if not paths else ["diff", "--cached", *paths]
    staged = _run_git(root, diff_args).stdout.strip()
    placeholder = "(nothing staged yet - will stage given paths first)"
    return f"Commit message: {message}\n\n{staged or placeholder}"


def git_commit(root: str, message: str, paths: list[str] = None) -> str:
    add_args = ["add", "-A"] if not paths else ["add", *paths]
    add_result = _run_git(root, add_args)
    if add_result.returncode != 0:
        raise ToolError(f"git add failed: {add_result.stderr.strip()}")

    commit_result = _run_git(root, ["commit", "-m", message])
    if commit_result.returncode != 0:
        return (
            f"git commit failed (exit {commit_result.returncode}): {commit_result.stderr.strip()}"
        )
    return commit_result.stdout.strip()


def preview_git_checkout_branch(root: str, branch: str) -> str:
    current = _current_branch(root)
    return f"Create and switch to new branch '{branch}' from '{current}'."


def git_checkout_branch(root: str, branch: str) -> str:
    result = _run_git(root, ["checkout", "-b", branch])
    if result.returncode != 0:
        return f"git checkout -b failed (exit {result.returncode}): {result.stderr.strip()}"
    return result.stdout.strip() or result.stderr.strip() or f"Switched to new branch '{branch}'."


def preview_git_push(root: str) -> str:
    """No branch/remote/force args exist on this tool at all -- it always
    pushes exactly 'the branch you're currently on' to 'origin', and
    refuses outright if that branch is main/master. Both refusals are
    enforced here AND in git_push itself, so a model that skips the
    preview still can't push to main/master through this tool."""
    branch = _current_branch(root)
    if branch in _PROTECTED_BRANCHES:
        return (
            f"REFUSED: current branch is '{branch}'. OpenCodingAgent never pushes directly to "
            "main/master -- use git_checkout_branch to create a feature branch first."
        )

    log = _run_git(root, ["log", f"origin/{branch}..HEAD", "--oneline"])
    if log.returncode != 0:
        commits = _run_git(root, ["log", "--oneline", "-10"]).stdout.strip() or "(no commits)"
        return f"Push new branch '{branch}' to origin (no upstream yet). Commits:\n{commits}"
    commits = log.stdout.strip() or "(nothing new to push)"
    return f"Push '{branch}' to origin. Commits:\n{commits}"


def git_push(root: str) -> str:
    branch = _current_branch(root)
    if branch in _PROTECTED_BRANCHES:
        raise ToolError(
            f"Refusing to push '{branch}' directly — OpenCodingAgent never pushes to "
            "main/master. Use git_checkout_branch to create a feature branch, then push "
            "that instead."
        )

    result = _run_git(root, ["push", "origin", f"HEAD:{branch}"])
    if result.returncode != 0:
        return f"git push failed (exit {result.returncode}): {result.stderr.strip()}"
    output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    return output or f"Pushed '{branch}' to origin."
