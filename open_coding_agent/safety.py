from rich.console import Console
from rich.syntax import Syntax


class SessionQuit(Exception):
    """Raised when the user chooses 'q' at a confirmation prompt."""


class AutoApprove:
    """In-session opt-in flag for file-edit-class risky tools. run_shell is
    intentionally excluded — always confirmed, even under auto-approve."""

    def __init__(self):
        self.files = False


def confirm_action(
    console: Console, tool_name: str, args: dict, preview: str, auto: AutoApprove
) -> bool:
    """Returns True if approved. Raises SessionQuit on 'q'. Shell commands
    always prompt regardless of the auto-approve flag."""
    always_confirm = tool_name == "run_shell"

    if auto.files and not always_confirm:
        console.print(f"[dim](auto-approved: {tool_name})[/dim]")
        return True

    console.print(
        f"\n[bold yellow]OpenCodingAgent wants to run:[/bold yellow] [bold]{tool_name}[/bold]"
    )
    if tool_name == "run_shell":
        console.print(f"  command: [cyan]{args.get('command')}[/cyan]")
        if args.get("cwd"):
            console.print(f"  cwd: {args['cwd']}")
    elif preview:
        console.print(Syntax(preview, "diff", theme="ansi_dark", background_color="default"))
    else:
        console.print(f"  {args}")

    try:
        choice = (
            console.input("[bold]Approve? [y/N/a=auto-approve edits/q=quit] [/bold]")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        raise SessionQuit() from None
    if choice == "q":
        raise SessionQuit()
    if choice == "a":
        auto.files = True
        return True
    return choice in ("y", "yes")
