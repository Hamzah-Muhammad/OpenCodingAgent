from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

BANNER = """[bold cyan]OpenCodingAgent[/bold cyan] - a free coding agent for your terminal.
Type a prompt and press Enter.
Commands: /model <name>  /help  /exit
"""


def print_banner(console: Console, model: str, root: str):
    console.print(Panel.fit(BANNER, border_style="cyan"))
    console.print(f"[dim]root: {root}  |  model: {model}[/dim]\n")


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

    with Live(console=console, refresh_per_second=12, transient=True) as live:
        for event_type, payload in client.turn_stream(
            messages, tools=tools, tool_choice="auto", model=model
        ):
            if event_type == "text":
                accumulated.append(payload)
                live.update(_response_panel("".join(accumulated)))
            elif event_type == "done":
                final = payload

    if accumulated:
        console.print(_response_panel("".join(accumulated)))

    return final


def print_tool_call(console: Console, name: str, args: dict):
    console.print(f"[dim]-> calling {name}({args})[/dim]")


def print_tool_result(console: Console, result: str, max_chars: int = 500):
    shown = result if len(result) <= max_chars else result[:max_chars] + "..."
    console.print(f"[dim]  {shown}[/dim]")


def print_error(console: Console, message: str):
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_usage(console: Console, turn_in: int, turn_out: int, session_totals: dict):
    session_in = session_totals["input_tokens"]
    session_out = session_totals["output_tokens"]
    console.print(
        f"[dim]tokens: {turn_in:,} in / {turn_out:,} out "
        f"(session: {session_in:,} in / {session_out:,} out)[/dim]"
    )


def print_compaction(console: Console, before: int, after: int):
    console.print(f"[dim](compacted conversation: {before} -> {after} messages)[/dim]")
