import io

import pytest
from rich.console import Console

from open_coding_agent.safety import AutoApprove, SessionQuit, confirm_action


def _console():
    return Console(file=io.StringIO(), force_terminal=False)


def _confirm(monkeypatch, reply: str) -> bool:
    console = _console()
    monkeypatch.setattr(console, "input", lambda prompt="": reply)
    return confirm_action(console, "write_file", {"path": "x.py"}, "diff", AutoApprove())


@pytest.mark.parametrize("reply", ["y", "Y", "yes", "YES", " yes "])
def test_confirm_action_accepts_yes_variants(monkeypatch, reply):
    assert _confirm(monkeypatch, reply) is True


@pytest.mark.parametrize("reply", ["n", "no", "", "nah"])
def test_confirm_action_rejects_anything_else(monkeypatch, reply):
    assert _confirm(monkeypatch, reply) is False


def test_confirm_action_a_sets_auto_approve(monkeypatch):
    console = _console()
    monkeypatch.setattr(console, "input", lambda prompt="": "a")
    auto = AutoApprove()
    assert confirm_action(console, "write_file", {}, "diff", auto) is True
    assert auto.files is True


def test_confirm_action_q_raises_session_quit(monkeypatch):
    console = _console()
    monkeypatch.setattr(console, "input", lambda prompt="": "q")
    with pytest.raises(SessionQuit):
        confirm_action(console, "write_file", {}, "diff", AutoApprove())


def test_confirm_action_run_shell_always_prompts_even_under_auto_approve(monkeypatch):
    console = _console()
    monkeypatch.setattr(console, "input", lambda prompt="": "y")
    auto = AutoApprove()
    auto.files = True
    assert confirm_action(console, "run_shell", {"command": "echo hi"}, "", auto) is True
