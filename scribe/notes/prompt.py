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
    # char_span is intentionally omitted from the schema: LLMs cannot reliably
    # produce per-utterance char offsets (they emit global transcript offsets),
    # and the CitationValidator strips out-of-bounds spans anyway. The
    # utterance_id is the real grounding guarantee.
    return {
        "type": "object",
        "properties": {
            "utterance_id": {"type": "string"},
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
    ids = [u.id for u in dialogue.utterances]
    first_id = ids[0] if ids else "u0000"
    last_id = ids[-1] if ids else "u0000"
    example = (
        '{"subjective": [{"text": "Patient reports chest pain.", '
        '"citations": [{"utterance_id": "u0003"}]}], '
        '"objective": [], "assessment": [{"text": "Likely musculoskeletal.", '
        '"citations": [{"utterance_id": "u0007"}]}], '
        '"plan": [{"text": "Rest and monitor.", "citations": [{"utterance_id": "u0009"}]}]}'
    )
    return (
        "You are a clinical scribe. Read the doctor–patient dialogue below and "
        "write a concise SOAP note grounded strictly in what was said. "
        "Do not invent information not present in the dialogue.\n\n"
        "IMPORTANT: For every claim you write, you MUST include a 'citations' "
        "array listing the utterance id(s) (e.g. \"u0001\") that support it. "
        f"Valid utterance ids range from {first_id} to {last_id} — "
        "copy them EXACTLY as they appear in the dialogue lines below. "
        "Do not invent or guess ids. A claim with a citation to an id not in "
        "the dialogue will be discarded.\n\n"
        f"Dialogue:\n{transcript}\n\n"
        "Respond with a single JSON object that is an INSTANCE of this schema "
        "(not the schema itself). The top-level keys must be "
        "'subjective', 'objective', 'assessment', 'plan' — each mapping to an "
        "array of claim objects. Example response shape:\n"
        f"{example}\n\n"
        "Schema for reference:\n"
        f"{json.dumps(SOAP_SCHEMA, indent=2)}\n"
    )
