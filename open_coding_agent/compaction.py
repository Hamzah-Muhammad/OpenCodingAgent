"""Conversation compaction: once a session's message history grows past a
threshold, collapse older turns into one durable-facts summary instead of
resending the full verbatim transcript on every remaining turn. Free/small
models have thinner context windows and a long resent transcript burns
rate-limit budget fast, so this matters more here than it would against a
large paid model.

The one thing this has to get right: never cut in the middle of an
assistant tool_calls -> tool result exchange. The agent's own turn loop
only ever gives role "user" to a message it appended for genuine new user
input (tool results are role "tool", never "user") -- so cutting exactly
at a "user" message is always a clean turn boundary, guaranteed, with no
need to inspect tool_call_id pairing at all.
"""

from typing import Optional

# Trigger threshold and how much recent history to always keep verbatim.
# Deliberately conservative defaults, not exposed as a CLI flag yet.
COMPACT_AFTER_MESSAGES = 40
KEEP_RECENT_MESSAGES = 10

_SUMMARY_INSTRUCTION = (
    "Summarize this conversation so far into durable facts only: decisions made, files "
    "touched and why, constraints established, anything that would matter to a "
    "continuation of this work. Be concise -- bullet points, no narration. Drop anything "
    "already resolved and no longer relevant."
)


def should_compact(messages: list[dict]) -> bool:
    return len(messages) > COMPACT_AFTER_MESSAGES


def _find_cut_index(messages: list[dict], search_from: int) -> Optional[int]:
    for i in range(search_from, len(messages)):
        if messages[i]["role"] == "user":
            return i
    return None


def compact(client, messages: list[dict], model: str = None) -> tuple[list[dict], Optional[dict]]:
    """Returns (new_messages, usage_of_the_summarization_call_or_None).
    new_messages is unchanged from the input if there's nothing safe to
    compact yet (no user-role boundary found in the search window)."""
    if len(messages) <= COMPACT_AFTER_MESSAGES:
        return messages, None

    search_from = max(1, len(messages) - KEEP_RECENT_MESSAGES)
    cut = _find_cut_index(messages, search_from)
    if cut is None or cut <= 1:
        return messages, None  # no safe boundary to compact around yet

    system = messages[0]
    to_summarize = messages[1:cut]
    recent = messages[cut:]

    summary_request = to_summarize + [{"role": "user", "content": _SUMMARY_INSTRUCTION}]
    result = client.turn(summary_request, tools=None, model=model)
    summary_text = (result["message"].get("content") or "").strip() or "(summary unavailable)"

    new_messages = [
        system,
        {
            "role": "user",
            "content": f"[{len(to_summarize)} earlier messages summarized]\n{summary_text}",
        },
        {
            "role": "assistant",
            "content": "Got it — continuing with that context.",
            "tool_calls": None,
        },
        *recent,
    ]
    return new_messages, result.get("usage")
