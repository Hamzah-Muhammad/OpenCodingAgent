"""Two things a coding agent must never do: send a secrets file to the model,
or silently rewrite a file's line endings."""

import pytest

from open_coding_agent.tools import fs, search


def test_read_env_is_refused(tmp_path):
    (tmp_path / ".env").write_text("NVIDIA_API_KEY=real\n")
    with pytest.raises(fs.ToolError, match="secrets file"):
        fs.read_file(str(tmp_path), ".env")


def test_env_example_is_still_readable(tmp_path):
    (tmp_path / ".env.example").write_text("NVIDIA_API_KEY=\n")
    assert fs.read_file(str(tmp_path), ".env.example") == "NVIDIA_API_KEY=\n"


@pytest.mark.parametrize(
    "name", [".env.production", "server.pem", "id_rsa", "credentials-prod.json", "secrets.yaml"]
)
def test_secret_patterns_match_on_basename(name):
    assert fs.is_secret_path(name)
    assert fs.is_secret_path(f"config/{name}")
    assert fs.is_secret_path(f"config\\{name}")


def test_write_edit_and_preview_of_secrets_are_refused(tmp_path):
    with pytest.raises(fs.ToolError, match="secrets file"):
        fs.write_file(str(tmp_path), "deploy.key", "x")
    with pytest.raises(fs.ToolError, match="secrets file"):
        fs.edit_file(str(tmp_path), ".env", "a", "b")
    with pytest.raises(fs.ToolError, match="secrets file"):
        fs.preview_edit_file(str(tmp_path), ".env", "a", "b")
    assert not (tmp_path / "deploy.key").exists()


def test_list_dir_hides_git(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "a.py").write_text("")
    assert fs.list_dir(str(tmp_path)) == "a.py"


def test_search_never_surfaces_a_secrets_file(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=abc123\n")
    (tmp_path / "app.py").write_text("token = load('TOKEN')\n")
    out = search.search_files(str(tmp_path), pattern="TOKEN")
    assert "app.py" in out
    assert ".env" not in out
    assert ".env" not in search.search_files(str(tmp_path), glob="*")


def test_edit_preserves_crlf(tmp_path):
    f = tmp_path / "win.txt"
    f.write_bytes(b"one\r\ntwo\r\nthree\r\n")
    # The model sends \n; the file's own style wins.
    fs.edit_file(str(tmp_path), "win.txt", "two\nthree", "2\n3\n4")
    assert f.read_bytes() == b"one\r\n2\r\n3\r\n4\r\n"


def test_edit_preserves_lf_even_on_windows(tmp_path):
    f = tmp_path / "unix.txt"
    f.write_bytes(b"one\ntwo\n")
    fs.edit_file(str(tmp_path), "unix.txt", "two", "2")
    assert f.read_bytes() == b"one\n2\n"


def test_rewrite_of_a_crlf_file_stays_crlf(tmp_path):
    f = tmp_path / "win.txt"
    f.write_bytes(b"a\r\n")
    fs.write_file(str(tmp_path), "win.txt", "b\nc\n")
    assert f.read_bytes() == b"b\r\nc\r\n"


def test_preview_edit_on_a_crlf_file_shows_a_clean_diff(tmp_path):
    f = tmp_path / "win.txt"
    f.write_bytes(b"one\r\ntwo\r\n")
    diff = fs.preview_edit_file(str(tmp_path), "win.txt", "two", "2")
    assert "-two" in diff and "+2" in diff
