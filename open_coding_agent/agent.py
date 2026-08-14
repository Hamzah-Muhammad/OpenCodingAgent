import json

from rich.console import Console

from open_coding_agent import ui
from open_coding_agent.compaction import compact, should_compact
from open_coding_agent.config import Config
from open_coding_agent.memory import load_system_prompt
from open_coding_agent.nvidia_client import NvidiaClient, NvidiaError
from open_coding_agent.safety import AutoApprove, SessionQuit, confirm_action
from open_coding_agent.tools import DANGER_CLASS, EXECUTORS, PREVIEWS, TOOL_SCHEMAS, ToolError

# Hard cap on tool-call round trips per user message. Without this, a
# weak/free model stuck oscillating on a bad tool call (or repeatedly
# emitting malformed arguments) just runs forever, burning turns and
# rate-limit budget with no way out short of Ctrl+C.
MAX_TOOL_TURNS = 25


def _execute_tool(console: Console, cfg: Config, auto: AutoApprove, name: str, args: dict) -> str:
    if name not in EXECUTORS:
        return f"Unknown tool: {name}"

    danger = DANGER_CLASS.get(name, "risky")
    if danger == "risky":
        preview_fn = PREVIEWS.get(name)
        preview = ""
        try:
            preview = preview_fn(cfg.root, **args) if preview_fn else ""
        except Exception as e:  # preview generation must never crash the session
            preview = f"(couldn't render preview: {e})"
        approved = confirm_action(console, name, args, preview, auto)
        if not approved:
            return (
                "User declined to run this action. Do not repeat the identical "
                "tool call — ask a clarifying question or propose a different approach."
            )
    else:
        ui.print_tool_call(console, name, args)

    try:
        result = EXECUTORS[name](cfg.root, **args)
    except ToolError as e:
        result = f"Tool error: {e}"
    except TypeError as e:
        result = f"Invalid arguments for {name}: {e}"
    except Exception as e:  # last-resort guard so a tool bug never kills the session
        result = f"Unexpected error running {name}: {e}"

    ui.print_tool_result(console, result)
    return result


def _accumulate_usage(session_usage: dict, usage: dict | None) -> None:
    if not usage:
        return
    session_usage["input_tokens"] += usage.get("input_tokens") or 0
    session_usage["output_tokens"] += usage.get("output_tokens") or 0


def _run_tool_loop(
    console: Console,
    cfg: Config,
    client: NvidiaClient,
    auto: AutoApprove,
    messages: list[dict],
    session_usage: dict,
) -> None:
    """Keeps calling the model and executing whatever tools it asks for,
    feeding results back, until the model stops requesting tools, the user
    quits mid-turn, a call fails, or MAX_TOOL_TURNS is hit. session_usage is
    accumulated in place on every successful call, even if the loop later
    hits the turn cap or gets cancelled -- tokens already spent still
    count."""
    turns = 0
    while True:
        turns += 1
        if turns > MAX_TOOL_TURNS:
            ui.print_error(
                console,
                f"Hit the {MAX_TOOL_TURNS}-turn limit for this message without finishing "
                "-- stopping here rather than looping forever. Send another message to "
                "continue (the conversation so far is kept).",
            )
            return

        try:
            result = ui.stream_assistant(console, client, messages, TOOL_SCHEMAS, cfg.model)
        except NvidiaError as e:
            ui.print_error(console, str(e))
            messages.pop()  # don't leave a dangling user turn the model never saw
            return

        if result is None:  # shouldn't happen -- the stream always ends in "done"
            ui.print_error(console, "Stream ended without a response.")
            messages.pop()
            return

        _accumulate_usage(session_usage, result.get("usage"))

        msg = result["message"]
        messages.append(
            {
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": msg.get("tool_calls"),
            }
        )

        if result["finish_reason"] != "tool_calls":
            if not msg.get("content"):
                console.print("[dim](no response)[/dim]")
            return

        quit_requested = False
        for tc in msg["tool_calls"] or []:
            name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments") or "{}"

            if quit_requested:
                tool_result = "Cancelled by user (session quit)."
            else:
                try:
                    args = json.loads(raw_args) if raw_args != "null" else {}
                except json.JSONDecodeError as e:
                    tool_result = f"Invalid JSON arguments from model: {e}"
                else:
                    try:
                        tool_result = _execute_tool(console, cfg, auto, name, args)
                    except SessionQuit:
                        quit_requested = True
                        tool_result = "Cancelled by user (session quit)."

            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})

        if quit_requested:
            console.print("[dim](turn cancelled)[/dim]")
            return
        # otherwise loop again: feed tool results back to the model


def run_session(cfg: Config):
    console = Console()
    client = NvidiaClient(cfg.api_key)
    auto = AutoApprove()
    messages: list[dict] = [{"role": "system", "content": load_system_prompt()}]
    session_usage = {"input_tokens": 0, "output_tokens": 0}

    ui.print_banner(console, cfg.model, cfg.root)

    while True:
        try:
            user_input = console.input("[bold blue]you>[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            break
        if user_input == "/help":
            console.print("Commands: /model <name>  /exit")
            continue
        if user_input.startswith("/model "):
            cfg.model = user_input.split(" ", 1)[1].strip()
            console.print(f"[dim]model set to {cfg.model}[/dim]")
            continue

        messages.append({"role": "user", "content": user_input})

        before = dict(session_usage)
        _run_tool_loop(console, cfg, client, auto, messages, session_usage)
        turn_in = session_usage["input_tokens"] - before["input_tokens"]
        turn_out = session_usage["output_tokens"] - before["output_tokens"]
        if turn_in or turn_out:
            ui.print_usage(console, turn_in, turn_out, session_usage)

        if should_compact(messages):
            try:
                new_messages, compaction_usage = compact(client, messages, model=cfg.model)
            except NvidiaError as e:
                ui.print_error(console, f"Compaction skipped: {e}")
            else:
                _accumulate_usage(session_usage, compaction_usage)
                if len(new_messages) < len(messages):
                    ui.print_compaction(console, len(messages), len(new_messages))
                messages = new_messages
