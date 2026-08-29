from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel

_BANNER_HINTS = "   ".join(
    (
        "[cyan]/help[/cyan] [dim]commands[/dim]",
        "[cyan]/model[/cyan] [dim]switch model[/dim]",
        "[cyan]/exit[/cyan] [dim]quit[/dim]",
    )
)

BANNER = (
    "[bold cyan]OpenCodingAgent[/bold cyan] "
    "[dim]- a free coding agent for your terminal[/dim]\n\n"
    "  [dim]Type a prompt and press Enter.[/dim]\n"
    f"  {_BANNER_HINTS}"
)


def print_banner(console: Console, model: str, root: str):
    console.print()
    console.print(Panel.fit(BANNER, border_style="cyan", padding=(1, 3)))

    # An aligned block rather than a run-on line: these are the two facts that
    # decide what any command will actually do, and "sandbox" is worth naming
    # explicitly so it is obvious the agent is confined.
    console.print(f"  [dim]{'sandbox':<9}[/dim] [dim]{escape(str(root))}[/dim]")
    console.print(f"  [dim]{'model':<9}[/dim] [dim]{escape(str(model))}[/dim]")
    console.print()


def _response_panel(text: str) -> Panel:
    return Panel(
        Markdown(text or ""), title="OpenCodingAgent", border_style="green", title_align="left"
    )


def stream_assistant(console: Console, client, messages: list[dict], tools, model) -> dict:
    """Drives client.turn_stream(), live-updating a panel as text arrives
    instead of waiting for the whole response. Returns the final "done"
    event's payload -- identical shape to what client.turn() returns
    non-streamed, so callers don't need to know streaming happened at all.
    Raises whatever turn_stream() raises (NvidiaError) -- caller's
    responsibility to catch it, same as the non-streaming call.

    If the turn produced no visible text at all (a pure tool-calling round
    trip with nothing said beforehand), no panel is shown -- same as the
    non-streaming behavior for a tool-only turn."""
    accumulated = []
    final = None

    # A spinner while the model is still thinking, so a slow first token does
    # not look like a hang. Only on a real terminal: through a pipe the frames
    # are noise, and on a legacy code page they raise encoding errors.
    status = None
    if console.is_terminal:
        status = console.status("[dim]thinking...[/dim]", spinner="dots")
        status.start()

    live = None
    try:
        for event_type, payload in client.turn_stream(
            messages, tools=tools, tool_choice="auto", model=model
        ):
            if status is not None:
                status.stop()
                status = None
            if event_type == "text":
                accumulated.append(payload)
                if live is None:
                    live = Live(console=console, refresh_per_second=12, transient=True)
                    live.start()
                live.update(_response_panel("".join(accumulated)))
            elif event_type == "done":
                final = payload
    finally:
        if status is not None:
            status.stop()
        if live is not None:
            live.stop()

    # Whitespace-only output still counts as "text arrived" and would draw an
    # empty green panel between tool calls -- a titled box with nothing in it.
    joined = "".join(accumulated)
    if joined.strip():
        console.print(_response_panel(joined))

    return final


# Arguments worth showing inline for each tool, in display order. Anything not
# listed is summarised rather than printed: dumping the raw dict meant a single
# write_file scrolled the whole file body past the user, burying the actual
# conversation.
_TOOL_KEY_ARGS = {
    "read_file": ("path",),
    "write_file": ("path",),
    "edit_file": ("path",),
    "list_dir": ("path",),
    "search_files": ("pattern", "glob"),
    "git_status": (),
    "git_diff": (),
    "run_shell": ("command",),
    "git_commit": ("message",),
    "git_checkout_branch": ("branch",),
    "git_push": (),
    "pr_create": ("title",),
}

_MAX_ARG_CHARS = 60
_MAX_RESULT_LINES = 6


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def summarize_tool_args(name: str, args: dict) -> str:
    """One short line describing a tool call, never the full payload."""
    if not isinstance(args, dict):
        return str(args)[:_MAX_ARG_CHARS]

    parts: list[str] = []
    for key in _TOOL_KEY_ARGS.get(name, tuple(args)[:2]):
        if key not in args:
            continue
        value = str(args[key]).replace("\n", " ")
        if len(value) > _MAX_ARG_CHARS:
            value = value[: _MAX_ARG_CHARS - 3] + "..."
        parts.append(value)

    # Bulk payloads get a size instead of their contents.
    for key in ("content", "new_text", "text"):
        if isinstance(args.get(key), str):
            parts.append(_format_size(len(args[key])))
            break

    return "  ".join(parts)


def print_tool_call(console: Console, name: str, args: dict):
    detail = summarize_tool_args(str(name), args if isinstance(args, dict) else {})
    label = f"[cyan]{escape(str(name))}[/cyan]"
    if detail:
        console.print(f"  [dim]>[/dim] {label} [dim]{escape(detail)}[/dim]")
    else:
        console.print(f"  [dim]>[/dim] {label}")


def print_tool_result(console: Console, result: str, max_chars: int = 500):
    shown = result if len(result) <= max_chars else result[:max_chars] + "..."

    # A failing tool used to look exactly like a succeeding one -- same dim
    # grey -- so a refusal or error scrolled by unnoticed mid-run. Failures
    # print in full: they are short and they are the ones worth reading.
    lowered = shown.lstrip().lower()
    failed = lowered.startswith(("error", "failed", "refus", "cannot", "not allowed", "no such"))
    style = "red" if failed else "dim"

    lines = shown.splitlines() or [""]
    if not failed and len(lines) > _MAX_RESULT_LINES:
        # A file read pasted its entire body into the transcript, pushing the
        # conversation off screen for content the user already owns.
        hidden = len(lines) - _MAX_RESULT_LINES
        lines = lines[:_MAX_RESULT_LINES] + [f"... ({hidden} more lines)"]

    for line in lines:
        console.print(f"    [{style}]{escape(line)}[/{style}]")


def print_error(console: Console, message: str):
    console.print(f"[bold red]Error:[/bold red] {escape(str(message))}")


def print_usage(console: Console, turn_in: int, turn_out: int, session_totals: dict):
    session_in = session_totals["input_tokens"]
    session_out = session_totals["output_tokens"]
    console.print(
        f"[dim]tokens: {turn_in:,} in / {turn_out:,} out "
        f"(session: {session_in:,} in / {session_out:,} out)[/dim]"
    )


def print_compaction(console: Console, before: int, after: int):
    console.print(f"[dim](compacted conversation: {before} -> {after} messages)[/dim]")
