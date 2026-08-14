import pytest

from open_coding_agent.tools.fs import (
    ToolError,
    edit_file,
    list_dir,
    preview_edit_file,
    read_file,
    write_file,
)


@pytest.fixture
def sandbox(tmp_path):
    (tmp_path / "a.txt").write_text("hello world\n")
    return tmp_path


def test_read_file(sandbox):
    assert read_file(str(sandbox), "a.txt") == "hello world\n"


def test_read_file_missing_raises(sandbox):
    with pytest.raises(ToolError):
        read_file(str(sandbox), "missing.txt")


def test_path_escape_refused(sandbox):
    with pytest.raises(ToolError):
        read_file(str(sandbox), "../outside.txt")


def test_list_dir(sandbox):
    (sandbox / "sub").mkdir()
    result = list_dir(str(sandbox))
    assert "a.txt" in result
    assert "sub/" in result


def test_write_file_creates_new(sandbox):
    write_file(str(sandbox), "new.txt", "content")
    assert (sandbox / "new.txt").read_text() == "content"


def test_edit_file_replaces_unique_text(sandbox):
    result = edit_file(str(sandbox), "a.txt", "hello", "goodbye")

    assert "Replaced 1" in result
    assert (sandbox / "a.txt").read_text() == "goodbye world\n"


def test_edit_file_missing_old_text_raises(sandbox):
    with pytest.raises(ToolError):
        edit_file(str(sandbox), "a.txt", "nonexistent", "x")


def test_edit_file_ambiguous_without_replace_all_raises(sandbox):
    (sandbox / "dup.txt").write_text("foo foo foo\n")
    with pytest.raises(ToolError):
        edit_file(str(sandbox), "dup.txt", "foo", "bar")


def test_edit_file_replace_all(sandbox):
    (sandbox / "dup.txt").write_text("foo foo foo\n")

    result = edit_file(str(sandbox), "dup.txt", "foo", "bar", replace_all=True)

    assert "Replaced 3" in result
    assert (sandbox / "dup.txt").read_text() == "bar bar bar\n"


def test_edit_file_missing_file_raises(sandbox):
    with pytest.raises(ToolError):
        edit_file(str(sandbox), "missing.txt", "a", "b")


def test_preview_edit_file_shows_diff(sandbox):
    preview = preview_edit_file(str(sandbox), "a.txt", "hello", "goodbye")

    assert "-hello world" in preview
    assert "+goodbye world" in preview


def test_preview_edit_file_missing_old_text_returns_message_not_raise(sandbox):
    preview = preview_edit_file(str(sandbox), "a.txt", "nonexistent", "x")

    assert "not found" in preview


def test_preview_edit_file_ambiguous_returns_message_not_raise(sandbox):
    (sandbox / "dup.txt").write_text("foo foo\n")

    preview = preview_edit_file(str(sandbox), "dup.txt", "foo", "bar")

    assert "appears 2 times" in preview
