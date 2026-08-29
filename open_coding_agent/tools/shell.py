import os
import subprocess

from open_coding_agent.tools.fs import ToolError, _resolve, assert_allowed_root

MAX_OUTPUT_CHARS = 4000


def run_shell(root: str, command: str, cwd: str = None, timeout: int = 60) -> str:
    # Independent of _resolve below: with no cwd argument the command would
    # otherwise run in whatever root was handed in, unchecked.
    assert_allowed_root(root)
    workdir = _resolve(root, cwd) if cwd else root
    if not os.path.isdir(workdir):
        raise ToolError(f"No such directory: {cwd}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]"

    output = (result.stdout or "") + (result.stderr or "")
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n[...output truncated...]"
    return f"exit code: {result.returncode}\n{output.strip()}"
