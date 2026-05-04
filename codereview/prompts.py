"""Prompt loading for the codereview teacher agent."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CODEREVIEW_SYSTEM_PROMPT = "codereview_system.txt"


def load_prompt(filename: str) -> str:
    """Load a prompt template from the repo-level prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def get_system_prompt() -> str:
    """Return the teacher-style instructions used for every model call."""
    return load_prompt(CODEREVIEW_SYSTEM_PROMPT)
