"""The tool loop must never leave the history in a state the provider will
reject on the next request."""

import io
from types import SimpleNamespace

from rich.console import Console

from open_coding_agent.agent import _rollback_to_last_user, _run_tool_loop
from open_coding_agent.safety import AutoApprove


def test_rollback_drops_the_orphaned_tool_calls_message():
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "done", "tool_calls": None},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "result"},
    ]
    _rollback_to_last_user(messages)
    assert [m["role"] for m in messages] == ["system", "user", "assistant"]


def test_rollback_on_the_first_turn_drops_just_the_user_message():
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    _rollback_to_last_user(messages)
    assert [m["role"] for m in messages] == ["system"]


def test_a_tool_call_truncated_by_max_tokens_is_discarded(tmp_path):
    class FakeClient:
        def turn_stream(self, messages, tools=None, tool_choice="auto", model=None):
            yield (
                "done",
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "1",
                                "type": "function",
                                "function": {"name": "read_file", "arguments": '{"path": "a.'},
                            }
                        ],
                    },
                    "finish_reason": "length",
                    "usage": {"input_tokens": 5, "output_tokens": 7},
                },
            )

    out = io.StringIO()
    console = Console(file=out, force_terminal=False, width=120)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    cfg = SimpleNamespace(model="m", root=str(tmp_path))

    _run_tool_loop(console, cfg, FakeClient(), AutoApprove(), messages, usage)

    assert [m["role"] for m in messages] == ["system"]
    assert usage == {"input_tokens": 5, "output_tokens": 7}  # tokens spent still count
    assert "ran out of output tokens" in out.getvalue()
