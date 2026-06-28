"""Prompt construction for the SOAP NoteGenerator. Pure function.

Phase 2: every claim must cite the utterance id(s) that ground it.
The model is shown the dialogue with labelled utterance ids ([u0001], etc.)
and instructed to populate the citations array per claim.
"""

from __future__ import annotations

import json
from typing import Any

from scribe.domain.types import Dialogue


def _span_ref_item() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "utterance_id": {"type": "string"},
            "char_span": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
            },
        },
        "required": ["utterance_id"],
        "additionalProperties": False,
    }


def _claim_item() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "citations": {
                "type": "array",
                "items": _span_ref_item(),
                "minItems": 1,
            },
        },
        "required": ["text", "citations"],
        "additionalProperties": False,
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
    """Render dialogue as a numbered, line-stable transcript for the LLM."""
    lines = []
    for u in dialogue.utterances:
        lines.append(f"[{u.id}] {u.role.value}: {u.text}")
    return "\n".join(lines)


def build_prompt(dialogue: Dialogue) -> str:
    """Grounded SOAP prompt — every claim must cite its supporting utterance ids."""
    transcript = render_dialogue_text(dialogue)
    return (
        "You are a clinical scribe. Read the doctor–patient dialogue below and "
        "write a concise SOAP note grounded strictly in what was said. "
        "Do not invent information not present in the dialogue.\n\n"
        "IMPORTANT: For every claim you write, you MUST include a 'citations' "
        "array listing the utterance id(s) (e.g. \"u0001\") that support it. "
        "Only cite utterance ids that appear in the dialogue. "
        "A claim without a valid citation will be discarded.\n\n"
        f"Dialogue:\n{transcript}\n\n"
        "Respond with JSON only, matching this schema exactly:\n"
        f"{json.dumps(SOAP_SCHEMA, indent=2)}\n"
    )
