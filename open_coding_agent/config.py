import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # walks up from cwd, picks up a project .env if present

DEFAULT_MODEL = "deepseek-ai/deepseek-v4-flash-0731"


@dataclass
class Config:
    api_key: str
    model: str
    root: str


def load_config(args) -> Config:
    api_key = args.api_key or os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "No NVIDIA_API_KEY set. Get a free one at https://build.nvidia.com "
            "and put it in .env or pass --api-key."
        )

    root = os.path.abspath(args.root) if args.root else os.getcwd()
    if not os.path.isdir(root):
        raise SystemExit(f"Working root does not exist: {root}")

    return Config(
        api_key=api_key,
        model=args.model or os.getenv("OPENCODINGAGENT_MODEL") or DEFAULT_MODEL,
        root=root,
    )
