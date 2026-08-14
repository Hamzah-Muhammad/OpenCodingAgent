import io

from rich.console import Console

from open_coding_agent.agent import MAX_TOOL_TURNS, _run_tool_loop
from open_coding_agent.config import Config
from open_coding_agent.safety import AutoApprove


def _console():
    return Console(file=io.StringIO(), force_terminal=False)


def _cfg(root) -> Config:
    return Config(api_key="", model="fake", root=str(root))


def _usage() -> dict:
    return {"input_tokens": 0, "output_tokens": 0}


class _InfiniteToolClient:
    """A model that keeps asking for the same safe tool call, forever."""

    def __init__(self):
        self.call_count = 0

    def turn_stream(self, messages, tools=None, tool_choice="auto", model=None):
        self.call_count += 1
        yield (
            "done",
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{self.call_count}",
                            "type": "function",
                            "function": {"name": "list_dir", "arguments": '{"path": "."}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        )


class _OneShotClient:
    """Streams its text in fragments, then finishes -- deliberately omits
    "usage" to also cover that a missing key doesn't break accumulation."""

    def turn_stream(self, messages, tools=None, tool_choice="auto", model=None):
        yield ("text", "do")
        yield ("text", "ne")
        yield (
            "done",
            {
                "message": {"role": "assistant", "content": "done", "tool_calls": None},
                "finish_reason": "stop",
            },
        )


def test_tool_loop_stops_at_max_turns(tmp_path):
    console = _console()
    client = _InfiniteToolClient()
    messages = [{"role": "user", "content": "loop forever"}]

    _run_tool_loop(console, _cfg(tmp_path), client, AutoApprove(), messages, _usage())

    assert client.call_count == MAX_TOOL_TURNS
    assert f"{MAX_TOOL_TURNS}-turn limit" in console.file.getvalue()


def test_tool_loop_conversation_preserved_after_hitting_cap(tmp_path):
    messages = [{"role": "user", "content": "loop forever"}]

    _run_tool_loop(
        _console(), _cfg(tmp_path), _InfiniteToolClient(), AutoApprove(), messages, _usage()
    )

    # the cap stops the loop, it doesn't discard what happened so far
    assert len(messages) > 1
    assert messages[0] == {"role": "user", "content": "loop forever"}


def test_tool_loop_stops_normally_when_model_finishes(tmp_path):
    console = _console()
    messages = [{"role": "user", "content": "hi"}]

    _run_tool_loop(console, _cfg(tmp_path), _OneShotClient(), AutoApprove(), messages, _usage())

    assert "done" in console.file.getvalue()
    assert messages[-1] == {"role": "assistant", "content": "done", "tool_calls": None}


def test_tool_loop_accumulates_usage_across_calls(tmp_path):
    session_usage = _usage()
    messages = [{"role": "user", "content": "loop forever"}]

    _run_tool_loop(
        _console(), _cfg(tmp_path), _InfiniteToolClient(), AutoApprove(), messages, session_usage
    )

    # one client.turn_stream() call per tool round trip, MAX_TOOL_TURNS of
    # them, each contributing 10 input / 2 output tokens
    assert session_usage["input_tokens"] == 10 * MAX_TOOL_TURNS
    assert session_usage["output_tokens"] == 2 * MAX_TOOL_TURNS


def test_tool_loop_missing_usage_in_response_does_not_crash(tmp_path):
    # _OneShotClient deliberately omits "usage" entirely -- older/partial
    # responses shouldn't break accumulation, just contribute nothing.
    session_usage = _usage()
    messages = [{"role": "user", "content": "hi"}]

    _run_tool_loop(
        _console(), _cfg(tmp_path), _OneShotClient(), AutoApprove(), messages, session_usage
    )

    assert session_usage == {"input_tokens": 0, "output_tokens": 0}
