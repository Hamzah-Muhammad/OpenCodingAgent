from types import SimpleNamespace

import pytest

from open_coding_agent.nvidia_client import NvidiaClient, NvidiaError


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(id_, name, arguments):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=arguments))


def _usage(prompt_tokens, completion_tokens):
    return SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


def _client_with_fake_create(fake_create) -> NvidiaClient:
    client = NvidiaClient("fake-key")
    client._client.chat.completions.create = fake_create
    return client


def test_turn_returns_text_response():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=_msg(content="hello"), finish_reason="stop")],
        usage=_usage(5, 2),
    )
    client = _client_with_fake_create(lambda **kw: response)

    result = client.turn([{"role": "user", "content": "hi"}])

    assert result["message"]["content"] == "hello"
    assert result["message"]["tool_calls"] is None
    assert result["finish_reason"] == "stop"
    assert result["usage"] == {"input_tokens": 5, "output_tokens": 2}


def test_turn_returns_tool_calls():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=_msg(tool_calls=[_tool_call("call_1", "list_dir", '{"path": "."}')]),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    client = _client_with_fake_create(lambda **kw: response)

    result = client.turn([{"role": "user", "content": "hi"}])

    assert result["finish_reason"] == "tool_calls"
    assert result["message"]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "list_dir", "arguments": '{"path": "."}'},
        }
    ]
    assert result["usage"] is None


def test_turn_wraps_connection_error():
    from openai import APIConnectionError

    def raise_it(**kw):
        raise APIConnectionError(request=SimpleNamespace())

    client = _client_with_fake_create(raise_it)

    with pytest.raises(NvidiaError):
        client.turn([{"role": "user", "content": "hi"}])


class _Chunk:
    def __init__(self, content=None, tool_calls=None, finish_reason=None, usage=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        ]
        self.usage = usage


class _ToolCallDelta:
    def __init__(self, index, id_=None, name=None, arguments=None):
        self.index = index
        self.id = id_
        self.function = (
            SimpleNamespace(name=name, arguments=arguments) if (name or arguments) else None
        )


def test_turn_stream_yields_text_then_done():
    chunks = [
        _Chunk(content="Hel"),
        _Chunk(content="lo"),
        _Chunk(finish_reason="stop", usage=_usage(5, 2)),
    ]
    client = _client_with_fake_create(lambda **kw: iter(chunks))

    events = list(client.turn_stream([{"role": "user", "content": "hi"}]))

    assert events[0] == ("text", "Hel")
    assert events[1] == ("text", "lo")
    assert events[2][0] == "done"
    assert events[2][1]["message"]["content"] == "Hello"
    assert events[2][1]["finish_reason"] == "stop"
    assert events[2][1]["usage"] == {"input_tokens": 5, "output_tokens": 2}


def test_turn_stream_assembles_tool_call_fragments_by_index():
    chunks = [
        _Chunk(tool_calls=[_ToolCallDelta(0, id_="call_1", name="list_dir")]),
        _Chunk(tool_calls=[_ToolCallDelta(0, arguments='{"path"')]),
        _Chunk(tool_calls=[_ToolCallDelta(0, arguments=': "."}')]),
        _Chunk(finish_reason="tool_calls"),
    ]
    client = _client_with_fake_create(lambda **kw: iter(chunks))

    events = list(client.turn_stream([{"role": "user", "content": "hi"}]))

    done = events[-1][1]
    assert done["message"]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "list_dir", "arguments": '{"path": "."}'},
        }
    ]


def test_turn_stream_wraps_status_error():
    from openai import APIStatusError

    fake_response = SimpleNamespace(status_code=429, request=SimpleNamespace(), headers={})

    def raise_it(**kw):
        raise APIStatusError("boom", response=fake_response, body=None)

    client = _client_with_fake_create(raise_it)

    with pytest.raises(NvidiaError):
        list(client.turn_stream([{"role": "user", "content": "hi"}]))
