import argparse
import sys

from open_coding_agent import __version__
from open_coding_agent.agent import run_session
from open_coding_agent.config import load_config
from open_coding_agent.nvidia_client import THINKING_MODES
from open_coding_agent.tools.fs import ALLOWED_ROOT_NAME


def main():
    # LLM output is free-form text we don't control; on a legacy Windows
    # console (cp1252 etc.) an unencodable character would otherwise crash
    # the whole session. Replace instead of raising.
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        prog="opencodingagent",
        description="OpenCodingAgent - a free coding agent for your terminal",
    )
    parser.add_argument("--model", help="Override the default model")
    parser.add_argument("--api-key", help="NVIDIA API key (or set NVIDIA_API_KEY)")
    parser.add_argument(
        "--root",
        help=(
            f"The sandbox directory; must be named {ALLOWED_ROOT_NAME} "
            f"(default: the current directory, or ~/{ALLOWED_ROOT_NAME})"
        ),
    )
    parser.add_argument(
        "--thinking",
        choices=THINKING_MODES,
        help=(
            "Reasoning mode for DeepSeek-style models: off (default, fast), on, or auto "
            "(send no flag). Also OPENCODINGAGENT_THINKING."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    try:
        cfg = load_config(args)
    except SystemExit as e:
        # Double-clicking the exe from the wrong folder used to flash the
        # message and close the window before anyone could read it.
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            if getattr(sys, "frozen", False) and sys.stdin.isatty():
                try:
                    input("\nPress Enter to close...")
                except EOFError:
                    pass
            sys.exit(1)
        raise
    run_session(cfg)


if __name__ == "__main__":
    main()
