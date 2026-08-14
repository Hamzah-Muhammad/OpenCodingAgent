import difflib
import os


class ToolError(Exception):
    """Raised for a tool-usage error; the message is fed back to the model
    as the tool result so it can adapt, instead of crashing the session."""


def _resolve(root: str, path: str) -> str:
    full = os.path.abspath(os.path.join(root, path))
    if os.path.commonpath([full, root]) != root:
        raise ToolError(f"Path '{path}' escapes the working root - refusing.")
    return full


def read_file(root: str, path: str, start_line: int = None, end_line: int = None) -> str:
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    with open(full, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if start_line or end_line:
        start = (start_line or 1) - 1
        end = end_line or len(lines)
        lines = lines[max(start, 0) : end]
    return "".join(lines)


def list_dir(root: str, path: str = ".") -> str:
    full = _resolve(root, path)
    if not os.path.isdir(full):
        raise ToolError(f"No such directory: {path}")
    entries = sorted(os.listdir(full))
    out = []
    for name in entries:
        marker = "/" if os.path.isdir(os.path.join(full, name)) else ""
        out.append(name + marker)
    return "\n".join(out) if out else "(empty)"


def preview_write_file(root: str, path: str, content: str) -> str:
    """Unified diff between the file's current contents and the proposed
    content, for the confirmation prompt. Empty string if the file is new."""
    full = _resolve(root, path)
    old_lines = []
    if os.path.isfile(full):
        with open(full, encoding="utf-8", errors="replace") as f:
            old_lines = f.readlines()
    new_lines = content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def write_file(root: str, path: str, content: str) -> str:
    full = _resolve(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


def _apply_edit(content: str, old_text: str, new_text: str, replace_all: bool) -> tuple[str, int]:
    count = content.count(old_text)
    if count == 0:
        raise ToolError(
            "old_text not found -- read the file first and copy the exact text to replace."
        )
    if count > 1 and not replace_all:
        raise ToolError(
            f"old_text appears {count} times -- make it unique, or pass replace_all=true."
        )
    new_content = (
        content.replace(old_text, new_text)
        if replace_all
        else content.replace(old_text, new_text, 1)
    )
    return new_content, (count if replace_all else 1)


def preview_edit_file(
    root: str, path: str, old_text: str, new_text: str, replace_all: bool = False
) -> str:
    """Returns the diff, or -- unlike most preview functions -- a plain
    explanation string if old_text can't be applied (not found, or
    ambiguous without replace_all), so that's visible before the
    approve/deny prompt rather than surfacing as a generic preview-render
    failure. edit_file itself still raises ToolError if run anyway."""
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    with open(full, encoding="utf-8", errors="replace") as f:
        content = f.read()

    try:
        new_content, _ = _apply_edit(content, old_text, new_text, replace_all)
    except ToolError as e:
        return str(e)

    old_lines = content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def edit_file(root: str, path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    with open(full, encoding="utf-8", errors="replace") as f:
        content = f.read()

    new_content, count = _apply_edit(content, old_text, new_text, replace_all)
    with open(full, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"Replaced {count} occurrence(s) in {path}"
