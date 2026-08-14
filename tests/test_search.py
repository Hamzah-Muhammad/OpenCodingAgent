import pytest

from open_coding_agent.tools.search import search_files


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "src" / "util.py").write_text("def bar():\n    return 2\n")
    (tmp_path / "README.md").write_text("# hi\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("should not be searched\n")
    return tmp_path


def test_lists_files_by_glob(project):
    result = search_files(str(project), glob="*.py")

    assert "src/main.py" in result
    assert "src/util.py" in result
    assert "README.md" not in result


def test_lists_all_files_by_default(project):
    result = search_files(str(project))

    assert "README.md" in result
    assert "src/main.py" in result


def test_skips_dotgit_directory(project):
    result = search_files(str(project))

    assert ".git" not in result


def test_grep_content(project):
    result = search_files(str(project), glob="*.py", pattern="def foo")

    assert "src/main.py:1:" in result
    assert "src/util.py" not in result


def test_grep_no_matches_returns_placeholder(project):
    result = search_files(str(project), pattern="nonexistent_xyz")

    assert result == "(no matches)"


def test_grep_respects_max_results(project):
    for i in range(5):
        (project / f"f{i}.py").write_text("target\n")

    result = search_files(str(project), glob="*.py", pattern="target", max_results=2)

    assert "capped at 2 results" in result


def test_missing_directory_raises(project):
    from open_coding_agent.tools.fs import ToolError

    with pytest.raises(ToolError):
        search_files(str(project), path="nonexistent")
