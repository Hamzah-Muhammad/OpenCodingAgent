"""Talks to NVIDIA's OpenAI-compatible chat-completions endpoint directly --
no backend service in between. NVIDIA's API (like Groq/Cerebras/OpenRouter)
implements the same request/response shape as OpenAI's own API, so the
standard `openai` SDK works against it by just pointing `base_url` at NVIDIA
instead of api.openai.com.

turn() and turn_stream() return/yield the same shape regardless of which one
you call, so agent.py and ui.py don't need to know or care whether a given
call was streamed.
"""

from typing import Optional

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaError(Exception):
    pass


class NvidiaClient:
    def __init__(self, api_key: str, timeout: float = 90.0):
        self._client = OpenAI(base_url=BASE_URL, api_key=api_key, timeout=timeout)

    def turn(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = self._client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            raise NvidiaError(f"Could not reach NVIDIA's API: {e}") from e
        except APIStatusError as e:
            raise NvidiaError(f"NVIDIA API error {e.status_code}: {e.message}") from e

        return _to_result(response.choices[0], getattr(response, "usage", None))

    def turn_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        """Yields ("text", str) for each visible text fragment as it arrives,
        then exactly one final ("done", dict) in the same shape turn()
        returns non-streamed.

        Tool-call argument fragments are NOT yielded incrementally -- a
        half-parsed JSON string is useless to show a user, so they're
        accumulated here (indexed by the provider's own delta.index, since
        multiple tool calls can interleave fragments across chunks) and only
        surface once complete, in the final event."""
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        text_parts = []
        tool_calls_by_index: dict[int, dict] = {}
        finish_reason = None
        usage = None

        try:
            stream = self._client.chat.completions.create(**kwargs)
            for chunk in stream:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage:
                    usage = {
                        "input_tokens": chunk_usage.prompt_tokens,
                        "output_tokens": chunk_usage.completion_tokens,
                    }

                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    text_parts.append(delta.content)
                    yield ("text", delta.content)

                for tc in delta.tool_calls or []:
                    entry = tool_calls_by_index.setdefault(
                        tc.index, {"id": None, "name": None, "arguments": ""}
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        except (APIConnectionError, APITimeoutError) as e:
            raise NvidiaError(f"Could not reach NVIDIA's API: {e}") from e
        except APIStatusError as e:
            raise NvidiaError(f"NVIDIA API error {e.status_code}: {e.message}") from e

        tool_calls = None
        if tool_calls_by_index:
            tool_calls = [
                {
                    "id": entry["id"],
                    "type": "function",
                    "function": {"name": entry["name"], "arguments": entry["arguments"]},
                }
                for _, entry in sorted(tool_calls_by_index.items())
            ]

        yield (
            "done",
            {
                "message": {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                    "tool_calls": tool_calls,
                },
                "finish_reason": finish_reason,
                "usage": usage,
            },
        )


def _to_result(choice, usage) -> dict:
    msg = choice.message
    tool_calls = None
    if msg.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    usage_out = None
    if usage:
        usage_out = {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
        }
    return {
        "message": {"role": "assistant", "content": msg.content, "tool_calls": tool_calls},
        "finish_reason": choice.finish_reason,
        "usage": usage_out,
    }
