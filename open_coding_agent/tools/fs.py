import difflib
import fnmatch
import os


class ToolError(Exception):
    """Raised for a tool-usage error; the message is fed back to the model
    as the tool result so it can adapt, instead of crashing the session."""


# Files whose contents must never enter the conversation: they would be sent
# to a third-party model and land in its logs. Matched on the basename, so the
# check cannot be dodged with a different relative path. Example/sample env
# files hold no real values and stay readable.
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "id_ecdsa*",
    "*.keystore",
    "credentials*.json",
    "secrets.*",
    ".npmrc",
    ".pypirc",
    ".netrc",
)
SECRET_EXCEPTIONS = (".env.example", ".env.sample", ".env.template")

# Never worth listing to a model: huge, noisy, and .git in particular is a way
# to read objects the working tree deliberately does not show.
HIDDEN_DIRS = {".git"}


def is_secret_path(path: str) -> bool:
    name = os.path.basename(str(path).replace("\\", "/").rstrip("/"))
    if name in SECRET_EXCEPTIONS:
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in SECRET_PATTERNS)


def _refuse_secret(path: str) -> None:
    if is_secret_path(path):
        raise ToolError(
            f"'{path}' looks like a secrets file (key, certificate or .env). Refusing to "
            "touch it: its contents must never reach the model. Ask the user to handle it."
        )


# The agent is allowed to operate in exactly one place: a directory with this
# name. Giving a model write access to a real machine is the risky part of a
# coding agent, so the boundary is a name, not a path -- a name cannot be
# widened by a typo, a stray `cd`, or a relative path in an argument.
ALLOWED_ROOT_NAME = "OpenCodingAgentRepo"


def root_is_allowed(root: str) -> bool:
    """True when `root`'s final component is the sandbox name.

    Both separators are normalised on every platform so a Windows path checked
    on a Linux CI runner gives the same answer (basename of a backslash path
    is the whole string there).
    """
    normalized = os.path.normpath(str(root).replace("\\", "/")).rstrip("/")
    return os.path.basename(normalized) == ALLOWED_ROOT_NAME


def assert_allowed_root(root: str) -> None:
    if not root_is_allowed(root):
        raise ToolError(
            f"OpenCodingAgent only operates inside a directory named "
            f"'{ALLOWED_ROOT_NAME}'; refusing to work in '{root}'."
        )


def _resolve(root: str, path: str) -> str:
    assert_allowed_root(root)

    # Containment is checked on the REAL path, with symlinks and Windows
    # directory junctions resolved. os.path.abspath only collapses "..", so a
    # junction sitting inside the sandbox and pointing anywhere on the disk
    # would otherwise pass this check: the path looks contained while the bytes
    # read and written are outside entirely. realpath resolves whatever
    # components exist, so a file about to be created works too.
    full = os.path.abspath(os.path.join(root, path))
    real_full = os.path.realpath(full)
    real_root = os.path.realpath(root)

    # The root must still be the allowed directory after resolution, or a
    # junction *named* OpenCodingAgentRepo pointing elsewhere would satisfy
    # the name check above and open the door.
    assert_allowed_root(real_root)

    try:
        escapes = os.path.commonpath([real_full, real_root]) != real_root
    except ValueError:
        # Windows raises ValueError rather than returning a mismatch when the
        # paths are on different drives (root on C:, path "D:\evil.txt").
        # Still an escape, just one commonpath cannot express as a prefix.
        escapes = True
    if escapes:
        raise ToolError(f"Path '{path}' escapes the working root - refusing.")

    # Return the real path so no caller can be handed a link that redirects
    # after the check has already passed.
    return real_full


def _read_raw(full: str) -> str:
    # newline="" keeps \r\n intact so an edit never silently rewrites a file's
    # line endings (Python's default translation plus a "w" write on Windows
    # turned every LF file into CRLF, one edit at a time).
    with open(full, encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def _write_raw(full: str, content: str) -> None:
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def _match_newlines(content: str, text: str) -> str:
    """Models emit \\n; make old/new text match the file's actual style."""
    if "\r\n" in content and "\r\n" not in text:
        return text.replace("\n", "\r\n")
    return text


def read_file(root: str, path: str, start_line: int = None, end_line: int = None) -> str:
    _refuse_secret(path)
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    # Translated read on purpose: the model sees clean LF either way, and
    # only edit/write need to know the file's real line endings.
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
    entries = sorted(e for e in os.listdir(full) if e not in HIDDEN_DIRS)
    out = []
    for name in entries:
        marker = "/" if os.path.isdir(os.path.join(full, name)) else ""
        out.append(name + marker)
    return "\n".join(out) if out else "(empty)"


def preview_write_file(root: str, path: str, content: str) -> str:
    """Unified diff between the file's current contents and the proposed
    content, for the confirmation prompt. Empty string if the file is new."""
    _refuse_secret(path)
    full = _resolve(root, path)
    old_lines = []
    if os.path.isfile(full):
        old_lines = _read_raw(full).splitlines(keepends=True)
    new_lines = _match_newlines("".join(old_lines), content).splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def write_file(root: str, path: str, content: str) -> str:
    _refuse_secret(path)
    full = _resolve(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if os.path.isfile(full):
        # A rewrite of an existing CRLF file keeps it CRLF.
        content = _match_newlines(_read_raw(full), content)
    _write_raw(full, content)
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
    _refuse_secret(path)
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    content = _read_raw(full)
    old_text = _match_newlines(content, old_text)
    new_text = _match_newlines(content, new_text)

    try:
        new_content, _ = _apply_edit(content, old_text, new_text, replace_all)
    except ToolError as e:
        return str(e)

    old_lines = content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def edit_file(root: str, path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    _refuse_secret(path)
    full = _resolve(root, path)
    if not os.path.isfile(full):
        raise ToolError(f"No such file: {path}")
    content = _read_raw(full)
    old_text = _match_newlines(content, old_text)
    new_text = _match_newlines(content, new_text)

    new_content, count = _apply_edit(content, old_text, new_text, replace_all)
    _write_raw(full, new_content)
    return f"Replaced {count} occurrence(s) in {path}"
