"""The `thinking` switch: DeepSeek V4 is a reasoning model and, left alone,
burns the whole output budget on hidden reasoning. Off by default."""

from types import SimpleNamespace

import pytest

from open_coding_agent import config as config_module
from open_coding_agent.nvidia_client import NvidiaClient
from open_coding_agent.ui import summarize_tool_args


def _capture_create():
    seen = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        message = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None
        )

    return seen, fake_create


def _turn(client, fake):
    client._client.chat.completions.create = fake
    client.turn([{"role": "user", "content": "hi"}], model="m")


def test_thinking_is_off_by_default():
    seen, fake = _capture_create()
    _turn(NvidiaClient("k"), fake)
    assert seen["extra_body"] == {"chat_template_kwargs": {"thinking": False}}


def test_thinking_on_sends_true():
    seen, fake = _capture_create()
    _turn(NvidiaClient("k", thinking="on"), fake)
    assert seen["extra_body"] == {"chat_template_kwargs": {"thinking": True}}


def test_thinking_auto_sends_no_flag_at_all():
    seen, fake = _capture_create()
    _turn(NvidiaClient("k", thinking="auto"), fake)
    assert "extra_body" not in seen


def test_invalid_thinking_mode_is_rejected():
    with pytest.raises(ValueError, match="thinking must be one of"):
        NvidiaClient("k", thinking="maybe")


def _args(**overrides):
    base = dict(api_key=None, model=None, root=None, thinking=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_config_thinking_defaults_off_reads_env_and_rejects_junk(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    monkeypatch.delenv("OPENCODINGAGENT_THINKING", raising=False)
    assert config_module.load_config(_args()).thinking == "off"

    monkeypatch.setenv("OPENCODINGAGENT_THINKING", "ON")
    assert config_module.load_config(_args()).thinking == "on"

    with pytest.raises(SystemExit, match="must be one of"):
        config_module.load_config(_args(thinking="maybe"))


def test_config_refusal_tells_the_user_how_to_set_up_a_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    wrong = tmp_path / "some-other-project"
    wrong.mkdir()
    with pytest.raises(SystemExit) as exc:
        config_module.load_config(_args(root=str(wrong)))
    assert f"mkdir {config_module.ALLOWED_ROOT_NAME}" in str(exc.value)
    assert "--root" in str(exc.value)


def test_summarize_tool_args_shows_key_args_not_payloads():
    assert summarize_tool_args("search_files", {"glob": "*.py", "pattern": "TODO"}) == "TODO  *.py"
    assert (
        summarize_tool_args("write_file", {"path": "a.py", "content": "x" * 2048}) == "a.py  2.0 KB"
    )
    assert summarize_tool_args("git_status", {}) == ""
