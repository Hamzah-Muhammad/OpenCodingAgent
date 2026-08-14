"""Search: grep file contents and/or list files matching a glob pattern,
jailed to root. One tool covers both jobs -- a query given greps, omitted
just lists matching paths -- instead of splitting into two tools that
would usually get called back-to-back anyway.
"""

import fnmatch
import os
import re

from open_coding_agent.tools.fs import ToolError, _resolve

MAX_RESULTS = 50
MAX_FILE_BYTES = 1_000_000  # skip anything this big -- almost certainly not source
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
    ".pytest_cache",
}


def search_files(
    root: str, glob: str = "*", pattern: str = None, path: str = ".", max_results: int = MAX_RESULTS
) -> str:
    start = _resolve(root, path)
    if not os.path.isdir(start):
        raise ToolError(f"No such directory: {path}")

    compiled = re.compile(pattern) if pattern else None
    results = []

    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]

        for name in sorted(filenames):
            if not fnmatch.fnmatch(name, glob):
                continue
            full = os.path.join(dirpath, name)
            # Normalize to forward slashes so results are consistent across
            # platforms (os.path.relpath uses native separators, which would
            # otherwise make this tool's output -- and every test asserting
            # against it -- platform-dependent).
            rel = os.path.relpath(full, root).replace(os.sep, "/")

            if compiled is None:
                results.append(rel)
                if len(results) >= max_results:
                    return "\n".join(results) + f"\n[...capped at {max_results} results...]"
                continue

            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if compiled.search(line):
                            results.append(f"{rel}:{lineno}: {line.strip()}")
                            if len(results) >= max_results:
                                return (
                                    "\n".join(results)
                                    + f"\n[...capped at {max_results} results...]"
                                )
            except OSError:
                continue

    return "\n".join(results) if results else "(no matches)"
