"""Loads the agent's own system prompt from SYSTEM_PROMPT.md. A single flat
file is enough at this size -- no need for a tiered core/modules/index
pattern, which only pays off for a much larger, genuinely conditional
system prompt."""

import sys
from functools import lru_cache
from pathlib import Path


def _prompt_path() -> Path:
    # PyInstaller onefile extracts data files to sys._MEIPASS at runtime,
    # not next to this .py file -- see the packaging command in the README
    # for the --add-data flag that puts SYSTEM_PROMPT.md there.
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "open_coding_agent" / "SYSTEM_PROMPT.md"
    return Path(__file__).parent / "SYSTEM_PROMPT.md"


@lru_cache
def load_system_prompt() -> str:
    return _prompt_path().read_text(encoding="utf-8").strip()
