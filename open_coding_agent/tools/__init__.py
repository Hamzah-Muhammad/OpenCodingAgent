from open_coding_agent.tools import fs, git, github, search, shell
from open_coding_agent.tools.fs import ToolError
from open_coding_agent.tools.schemas import DANGER_CLASS, TOOL_SCHEMAS

# name -> executor(root, **kwargs) -> str
EXECUTORS = {
    "read_file": fs.read_file,
    "list_dir": fs.list_dir,
    "search_files": search.search_files,
    "git_status": lambda root, **kw: git.git_status(root),
    "git_diff": git.git_diff,
    "write_file": fs.write_file,
    "edit_file": fs.edit_file,
    "run_shell": shell.run_shell,
    "git_commit": git.git_commit,
    "git_checkout_branch": git.git_checkout_branch,
    "git_push": lambda root, **kw: git.git_push(root),
    "pr_create": github.pr_create,
}

# name -> preview(root, **kwargs) -> str | None, shown before a risky
# tool executes; omitted tools (safe ones) never need a preview.
PREVIEWS = {
    "write_file": fs.preview_write_file,
    "edit_file": fs.preview_edit_file,
    "git_commit": git.preview_git_commit,
    "git_checkout_branch": git.preview_git_checkout_branch,
    "git_push": lambda root, **kw: git.preview_git_push(root),
    "pr_create": github.preview_pr_create,
}

__all__ = ["EXECUTORS", "PREVIEWS", "DANGER_CLASS", "TOOL_SCHEMAS", "ToolError"]
