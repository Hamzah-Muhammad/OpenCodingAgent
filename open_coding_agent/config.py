import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from open_coding_agent.nvidia_client import THINKING_MODES
from open_coding_agent.tools.fs import ALLOWED_ROOT_NAME, root_is_allowed

load_dotenv()  # walks up from cwd, picks up a project .env if present

DEFAULT_MODEL = "deepseek-ai/deepseek-v4-flash-0731"


def _default_root() -> str:
    """Sandbox to use when --root is not given.

    The current directory if it already is the sandbox, else the sandbox in
    the home folder if one exists, else the current directory, which
    load_config then refuses with instructions. Deliberately nothing more
    clever: the agent must never end up somewhere the user did not choose,
    and the banner always prints the sandbox it settled on.
    """
    cwd = os.getcwd()
    if root_is_allowed(cwd):
        return cwd
    home_sandbox = Path.home() / ALLOWED_ROOT_NAME
    if home_sandbox.is_dir():
        return str(home_sandbox)
    return cwd


@dataclass
class Config:
    api_key: str
    model: str
    root: str
    thinking: str = "off"


def load_config(args) -> Config:
    api_key = args.api_key or os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "No NVIDIA_API_KEY set. Get a free one at https://build.nvidia.com "
            "and put it in .env or pass --api-key."
        )

    root = os.path.abspath(args.root) if args.root else _default_root()
    if not root_is_allowed(root):
        raise SystemExit(
            "OpenCodingAgent only works inside a directory named "
            f"'{ALLOWED_ROOT_NAME}'.\n"
            f"  refused: {root}\n\n"
            "That directory is the sandbox: the agent writes files and runs shell "
            "commands, so it is confined to one place, chosen by name rather than by "
            "path so a typo or a stray `cd` can never widen it.\n"
            f"  1. mkdir {ALLOWED_ROOT_NAME}    (anywhere, e.g. in your home folder)\n"
            "  2. put or clone the project you want it to work on inside\n"
            f"  3. run OpenCodingAgent from there, or pass --root <path>/{ALLOWED_ROOT_NAME}"
        )
    if not os.path.isdir(root):
        raise SystemExit(f"Working root does not exist: {root}")

    thinking = (
        getattr(args, "thinking", None) or os.getenv("OPENCODINGAGENT_THINKING") or "off"
    ).lower()
    if thinking not in THINKING_MODES:
        raise SystemExit(
            f"--thinking / OPENCODINGAGENT_THINKING must be one of {', '.join(THINKING_MODES)}; "
            f"got {thinking!r}."
        )

    return Config(
        api_key=api_key,
        model=args.model or os.getenv("OPENCODINGAGENT_MODEL") or DEFAULT_MODEL,
        root=root,
        thinking=thinking,
    )
