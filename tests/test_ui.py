import io

from rich.console import Console

from open_coding_agent.agent import _call_model


def _console():
    return Console(file=io.StringIO(), force_terminal=False)


class _TextClient:
    def turn_stream(self, messages, tools=None, tool_choice="auto", model=None):
        yield ("text", "Hel")
        yield ("text", "lo")
        yield (
            "done",
            {
                "message": {"role": "assistant", "content": "Hello", "tool_calls": None},
                "finish_reason": "stop",
                "usage": {"input_tokens": 5, "output_tokens": 2},
            },
        )


class _ToolOnlyClient:
    """No text at all -- straight to a tool call, nothing said first."""

    def turn_stream(self, messages, tools=None, tool_choice="auto", model=None):
        yield (
            "done",
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "list_dir", "arguments": "{}"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
                "usage": None,
            },
        )


def test_call_model_returns_final_done_payload():
    console = _console()

    result = _call_model(console, _TextClient(), [{"role": "user", "content": "hi"}], None)

    assert result["message"]["content"] == "Hello"
    assert result["finish_reason"] == "stop"
    assert result["usage"] == {"input_tokens": 5, "output_tokens": 2}


def test_call_model_renders_accumulated_text():
    console = _console()

    _call_model(console, _TextClient(), [{"role": "user", "content": "hi"}], None)

    assert "Hello" in console.file.getvalue()


def test_call_model_no_panel_for_tool_only_turn():
    console = _console()

    result = _call_model(
        console, _ToolOnlyClient(), [{"role": "user", "content": "list files"}], None
    )

    assert result["message"]["tool_calls"][0]["function"]["name"] == "list_dir"
    # no visible text was ever streamed, so nothing should be printed
    assert console.file.getvalue().strip() == ""
