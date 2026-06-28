"""Prompt construction for the SOAP NoteGenerator. Pure function.

Slice 0: plain prompt, no span-citation instructions. Phase 2 deepens this
to demand grounded citations + constrained JSON.
"""

from __future__ import annotations

import json
from typing import Any

from scribe.domain.types import Dialogue


def _claim_item() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            # Slice 0: citations omitted from the prompt; Phase 2 adds them.
        },
        "required": ["text"],
        "additionalProperties": True,
    }


SOAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subjective": {"type": "array", "items": _claim_item()},
        "objective": {"type": "array", "items": _claim_item()},
        "assessment": {"type": "array", "items": _claim_item()},
        "plan": {"type": "array", "items": _claim_item()},
    },
    "required": ["subjective", "objective", "assessment", "plan"],
    "additionalProperties": False,
}


def render_dialogue_text(dialogue: Dialogue) -> str:
    """Render dialogue as a numbered, line-stable transcript for the LLM.

    Utterance ids are stable (``u0001``...), so Phase-2 span citations can
    reference them by id without re-parsing.
    """
    lines = []
    for u in dialogue.utterances:
        lines.append(f"[{u.id}] {u.role.value}: {u.text}")
    return "\n".join(lines)


def build_prompt(dialogue: Dialogue) -> str:
    """Slice-0 plain SOAP prompt. Pure — no I/O, no model calls."""
    transcript = render_dialogue_text(dialogue)
    return (
        "You are a clinical scribe. Read the doctor–patient dialogue and write "
        "a concise SOAP note grounded strictly in what was said. Do not invent "
        "information not present in the dialogue.\n\n"
        f"Dialogue:\n{transcript}\n\n"
        "Respond with JSON only, matching this schema:\n"
        f"{json.dumps(SOAP_SCHEMA, indent=2)}\n"
    )
