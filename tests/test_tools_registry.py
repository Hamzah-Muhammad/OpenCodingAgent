"""One tool is described in three places -- its JSON schema and danger class in
schemas.py, its executor and preview in tools/__init__.py, its implementation
in its own module. Nothing at import time checks they agree; a name typo in
one map only surfaces at runtime as "Unknown tool". This pins them together."""

from open_coding_agent.tools import DANGER_CLASS, EXECUTORS, PREVIEWS, TOOL_SCHEMAS

SCHEMA_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}


def test_every_schema_has_an_executor_and_vice_versa():
    assert SCHEMA_NAMES == set(EXECUTORS)


def test_every_tool_has_a_danger_class():
    assert SCHEMA_NAMES == set(DANGER_CLASS)
    assert set(DANGER_CLASS.values()) <= {"safe", "risky"}


def test_previews_exist_only_for_risky_tools():
    # run_shell is risky but has no preview function: the literal command is
    # the preview, and confirm_action() already shows it.
    risky = {name for name, cls in DANGER_CLASS.items() if cls == "risky"}
    assert set(PREVIEWS) <= risky, "a safe tool never prompts, so it must not carry a preview"
    assert risky - set(PREVIEWS) == {"run_shell"}


def test_schema_names_are_unique():
    assert len(SCHEMA_NAMES) == len(TOOL_SCHEMAS)
