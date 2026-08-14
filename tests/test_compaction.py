from open_coding_agent.compaction import COMPACT_AFTER_MESSAGES, compact, should_compact


class _SummaryClient:
    def __init__(self, summary_text="- did X\n- decided Y"):
        self.summary_text = summary_text
        self.calls = []

    def turn(self, messages, tools=None, model=None):
        self.calls.append(messages)
        return {
            "message": {"role": "assistant", "content": self.summary_text, "tool_calls": None},
            "finish_reason": "stop",
            "usage": {"input_tokens": 500, "output_tokens": 40},
        }


def _turn(role, content="x", tool_calls=None):
    msg = {"role": role, "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return msg


def _long_transcript(n_user_turns: int) -> list[dict]:
    """A system message followed by n_user_turns of
    user -> assistant(tool_calls) -> tool -> assistant(final)."""
    messages = [{"role": "system", "content": "you are an agent"}]
    for i in range(n_user_turns):
        messages.append(_turn("user", f"do thing {i}"))
        messages.append(
            _turn(
                "assistant",
                None,
                tool_calls=[
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            )
        )
        messages.append({"role": "tool", "tool_call_id": f"call_{i}", "content": "ok"})
        messages.append(_turn("assistant", f"done with {i}", tool_calls=None))
    return messages


def test_should_compact_below_threshold():
    assert should_compact(_long_transcript(2)) is False


def test_should_compact_above_threshold():
    messages = _long_transcript(20)  # well over COMPACT_AFTER_MESSAGES
    assert len(messages) > COMPACT_AFTER_MESSAGES
    assert should_compact(messages) is True


def test_compact_noop_below_threshold():
    messages = _long_transcript(2)
    client = _SummaryClient()

    new_messages, usage = compact(client, messages)

    assert new_messages is messages
    assert usage is None
    assert client.calls == []


def test_compact_reduces_message_count_and_keeps_system():
    messages = _long_transcript(20)
    client = _SummaryClient()

    new_messages, usage = compact(client, messages)

    assert len(new_messages) < len(messages)
    assert new_messages[0] == messages[0]  # system message untouched
    assert usage == {"input_tokens": 500, "output_tokens": 40}


def test_compact_never_cuts_mid_tool_exchange():
    messages = _long_transcript(20)

    new_messages, _ = compact(_SummaryClient(), messages)

    # every message after the system+summary+ack preamble must be a role
    # that's safe to start a kept window on -- specifically, the first
    # "real" kept message must be role "user" (the boundary this whole
    # module is built around), never a dangling "tool" result.
    kept = new_messages[3:]
    assert kept  # the transcript is long enough that something is kept
    assert kept[0]["role"] == "user"


def test_compact_summary_appears_in_new_messages():
    messages = _long_transcript(20)
    client = _SummaryClient(summary_text="- summary marker here")

    new_messages, _ = compact(client, messages)

    assert any("summary marker here" in (m.get("content") or "") for m in new_messages)


def test_compact_returns_unchanged_if_no_safe_boundary_in_window():
    # one giant single turn, way over threshold, but only ONE user message
    # total (at index 1) -- there's no boundary inside the keep-recent
    # window, so compaction must skip rather than cut somewhere unsafe.
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "start"}]
    for i in range(60):
        messages.append(
            _turn(
                "assistant",
                None,
                tool_calls=[
                    {
                        "id": f"c{i}",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            )
        )
        messages.append({"role": "tool", "tool_call_id": f"c{i}", "content": "ok"})

    client = _SummaryClient()
    new_messages, usage = compact(client, messages)

    assert new_messages is messages
    assert usage is None
