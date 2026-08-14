TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file's contents, optionally a specific line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working root"},
                    "start_line": {"type": "integer", "description": "1-indexed, optional"},
                    "end_line": {"type": "integer", "description": "1-indexed inclusive, optional"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories at a path (directories end with /).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working root"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Find files by name pattern and/or search their contents by regex, under a path. "
                "Omit 'pattern' to just list files matching 'glob'; give both to grep within them. "
                "Use this instead of guessing paths or reading whole directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "glob": {
                        "type": "string",
                        "description": "Filename pattern, e.g. '*.py' (default: all files)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Regex to search contents; omit to just list matching files",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search under, relative to root (default '.')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show the working tree's git status (porcelain format).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show unstaged git diff, optionally scoped to one path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional, relative path"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Overwrite a file with new content, or create a new file. Prefer edit_file for "
                "a targeted change to a file that already exists — this replaces the whole file, "
                "so anything not in 'content' is gone. Requires user approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working root"},
                    "content": {"type": "string", "description": "The full new file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace an exact piece of text in an existing file with new text — a targeted "
                "search/replace, unlike write_file's full overwrite. old_text must match exactly "
                "(read the file first) and must be unique in the file unless replace_all is set. "
                "Requires user approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working root"},
                    "old_text": {"type": "string", "description": "Exact existing text to find"},
                    "new_text": {"type": "string", "description": "Text to replace it with"},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace every occurrence, not just a unique one",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a shell command in the working directory. Requires explicit user "
                "approval every time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact command to run"},
                    "cwd": {
                        "type": "string",
                        "description": "Optional working dir, relative to the working root",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage changes and create a git commit. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional specific paths to stage; omit to stage all",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout_branch",
            "description": "Create a new branch from HEAD and switch to it. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Name of the new branch"},
                },
                "required": ["branch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": (
                "Push the current branch to origin. No branch, remote, or force option can be "
                "specified — it always pushes exactly 'this branch' to 'origin', and refuses "
                "outright on main/master. Requires user approval."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pr_create",
            "description": (
                "Open a pull request from the current branch into main, via the gh CLI. The "
                "branch must already be pushed (git_push first) — refuses otherwise, and refuses "
                "outright on main/master. No base-branch or repo parameter exists — always "
                "targets main on the current repo. Requires user approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description, optional"},
                },
                "required": ["title"],
            },
        },
    },
]

# name -> "safe" (auto-runs) or "risky" (requires confirmation)
DANGER_CLASS = {
    "read_file": "safe",
    "list_dir": "safe",
    "search_files": "safe",
    "git_status": "safe",
    "git_diff": "safe",
    "write_file": "risky",
    "edit_file": "risky",
    "run_shell": "risky",
    "git_commit": "risky",
    "git_checkout_branch": "risky",
    "git_push": "risky",
    "pr_create": "risky",
}
