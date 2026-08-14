import argparse
import sys

from open_coding_agent.agent import run_session
from open_coding_agent.config import load_config


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
        help="Directory the agent's file/shell/git tools are jailed to (default: cwd)",
    )
    args = parser.parse_args()

    cfg = load_config(args)
    run_session(cfg)


if __name__ == "__main__":
    main()
