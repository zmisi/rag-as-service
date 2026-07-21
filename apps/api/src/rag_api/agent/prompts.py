"""Load versioned prompt files from apps/api/prompts/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache
def load_system_prompt() -> str:
    path = _PROMPTS_ROOT / "system" / "default.md"
    return path.read_text(encoding="utf-8").strip()


@lru_cache
def load_grounding_rules() -> str:
    path = _PROMPTS_ROOT / "rules" / "grounding.md"
    return path.read_text(encoding="utf-8").strip()
