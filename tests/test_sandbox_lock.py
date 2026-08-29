"""The sandbox is the safety story of this project, so it gets its own tests.

OpenCodingAgent writes files and runs shell commands on a real machine. The
boundary is a directory *name*: a name cannot be widened by a typo, a stray
`cd`, or a relative path in a tool argument the way a path prefix can.
"""

import os
import subprocess

import pytest

from open_coding_agent.tools import fs


def _make_link(link: str, target: str) -> bool:
    """Windows directory junction; POSIX symlink. False when unavailable."""
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, target], capture_output=True, check=False
        )
    else:
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError:
            return False
    return os.path.isdir(link)


def test_root_must_be_named_after_the_sandbox(tmp_path):
    wrong = tmp_path.parent / "SomeOtherProject"
    wrong.mkdir(exist_ok=True)
    with pytest.raises(fs.ToolError, match="only operates inside a directory named"):
        fs._resolve(str(wrong), "file.txt")


def test_root_name_check_is_separator_agnostic():
    # A Windows path evaluated on a Linux CI runner must give the same answer:
    # basename of a backslash path is the whole string there.
    assert fs.root_is_allowed(r"C:\Apps\Projects\OpenCodingAgentRepo")
    assert fs.root_is_allowed("/home/x/OpenCodingAgentRepo")
    assert fs.root_is_allowed("C:/Apps/Projects/OpenCodingAgentRepo/")
    assert not fs.root_is_allowed(r"C:\Apps\Projects")
    assert not fs.root_is_allowed("/home/x/OpenCodingAgentRepoo")


def test_parent_traversal_is_refused(tmp_path):
    outside = tmp_path.parent / "OUTSIDE"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("outside")
    with pytest.raises(fs.ToolError, match="escapes the working root"):
        fs._resolve(str(tmp_path), "../OUTSIDE/secret.txt")


def test_absolute_path_outside_root_is_refused(tmp_path):
    target = os.path.abspath(os.sep + "evil.txt")
    with pytest.raises(fs.ToolError, match="escapes the working root"):
        fs._resolve(str(tmp_path), target)


def test_junction_inside_the_sandbox_cannot_escape(tmp_path):
    """abspath collapses ".." but does not resolve links.

    A junction planted inside the sandbox used to pass containment while the
    bytes read and written were outside it entirely.
    """
    outside = tmp_path.parent / "OUTSIDE_JUNCTION"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("outside the sandbox")

    if not _make_link(str(tmp_path / "escape"), str(outside)):
        pytest.skip("cannot create junctions/symlinks in this environment")

    with pytest.raises(fs.ToolError, match="escapes the working root"):
        fs._resolve(str(tmp_path), "escape/secret.txt")


def test_a_link_named_like_the_sandbox_is_still_refused(tmp_path):
    """Naming a junction OpenCodingAgentRepo must not satisfy the lock."""
    outside = tmp_path.parent / "ELSEWHERE"
    outside.mkdir(exist_ok=True)
    fake = tmp_path.parent / "fake" / fs.ALLOWED_ROOT_NAME
    fake.parent.mkdir(parents=True, exist_ok=True)

    if not _make_link(str(fake), str(outside)):
        pytest.skip("cannot create junctions/symlinks in this environment")

    with pytest.raises(fs.ToolError, match="only operates inside a directory named"):
        fs._resolve(str(fake), "secret.txt")


def test_ordinary_paths_inside_the_sandbox_still_work(tmp_path):
    (tmp_path / "ok.txt").write_text("fine")
    assert fs._resolve(str(tmp_path), "ok.txt").endswith("ok.txt")


def test_shell_refuses_a_root_outside_the_sandbox(tmp_path):
    from open_coding_agent.tools import shell

    wrong = tmp_path.parent / "NotTheSandbox"
    wrong.mkdir(exist_ok=True)
    with pytest.raises(fs.ToolError, match="only operates inside a directory named"):
        shell.run_shell(str(wrong), "echo hi")


def test_git_refuses_a_root_outside_the_sandbox(tmp_path):
    from open_coding_agent.tools import git

    wrong = tmp_path.parent / "NotTheSandboxEither"
    wrong.mkdir(exist_ok=True)
    with pytest.raises(fs.ToolError, match="only operates inside a directory named"):
        git.git_status(str(wrong))
