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


class StreamRenderer:
    """Renders one streamed assistant turn: a spinner until the first event
    (so a slow first token does not look like a hang), a live panel that
    updates as text arrives, and the finished panel once the turn is over.

    It never touches the client. agent._call_model() drives the model and
    feeds text fragments in here, so the UI is a subscriber to the turn, not
    the thing that runs it: the loop can be driven headless with no renderer
    at all, and the model call has exactly one owner.

    If the turn produced no visible text (a pure tool-calling round trip with
    nothing said first), no panel is shown -- a titled box with nothing in it
    would just be noise between tool calls."""

    def __init__(self, console: Console):
        self._console = console
        self._parts: list[str] = []
        self._status = None
        self._live = None

    def __enter__(self):
        # Only on a real terminal: through a pipe the spinner frames are
        # noise, and on a legacy code page they raise encoding errors.
        if self._console.is_terminal:
            self._status = self._console.status("[dim]thinking...[/dim]", spinner="dots")
            self._status.start()
        return self

    def on_event(self) -> None:
        """Any event from the stream means the model has started answering."""
        if self._status is not None:
            self._status.stop()
            self._status = None

    def on_text(self, fragment: str) -> None:
        self._parts.append(fragment)
        if self._live is None:
            self._live = Live(console=self._console, refresh_per_second=12, transient=True)
            self._live.start()
        self._live.update(_response_panel("".join(self._parts)))

    def __exit__(self, *exc) -> None:
        if self._status is not None:
            self._status.stop()
        if self._live is not None:
            self._live.stop()
        # Whitespace-only output still counts as "text arrived" and would draw
        # an empty green panel between tool calls.
        joined = "".join(self._parts)
        if joined.strip():
            self._console.print(_response_panel(joined))


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
