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
        '{"subjective": ['
        '{"text": "Patient reports sharp chest pain that started this morning, rated 7/10.", '
        '"citations": [{"utterance_id": "u0003"}, {"utterance_id": "u0005"}]}, '
        '{"text": "No associated nausea, shortness of breath, or radiation to the arm.", '
        '"citations": [{"utterance_id": "u0009"}]}], '
        '"objective": ['
        '{"text": "No physical examination performed (teleconsultation).", '
        '"citations": [{"utterance_id": "u0001"}]}], '
        '"assessment": ['
        '{"text": "Likely musculoskeletal chest pain. No red flag features for cardiac cause.", '
        '"citations": [{"utterance_id": "u0021"}, {"utterance_id": "u0023"}]}], '
        '"plan": ['
        '{"text": "Advised regular ibuprofen 400 mg with food for 5 days.", '
        '"citations": [{"utterance_id": "u0025"}]}, '
        '{"text": "Return if pain worsens, spreads to jaw or arm, or if breathlessness develops.", '
        '"citations": [{"utterance_id": "u0027"}]}]}'
    )
    section_guide = (
        "SOAP section definitions — populate ALL four:\n"
        "  SUBJECTIVE   : What the patient reports — symptoms, onset, severity, character, "
        "associated features, relevant history, medications, allergies, family history, "
        "social history. Extract every clinically relevant detail the patient states.\n"
        "  OBJECTIVE    : Measurable findings — vitals, examination findings, test results. "
        "If this is a teleconsultation with no physical examination, write exactly one claim: "
        "\"No physical examination performed (teleconsultation).\" citing the opening utterance.\n"
        "  ASSESSMENT   : The clinician's working diagnosis or clinical impression — "
        "synthesise the diagnostic reasoning stated or clearly implied by the clinician. "
        "Include significant positive and negative findings that shape the impression.\n"
        "  PLAN         : Every management step the clinician recommended — medications "
        "(drug, dose, duration, instructions), safety-netting advice, follow-up instructions, "
        "referrals, lifestyle advice. One claim per distinct action.\n"
    )
    return (
        "You are an expert clinical scribe. Your task is to extract a complete, "
        "accurate SOAP note from the doctor–patient dialogue below.\n\n"
        f"{section_guide}\n"
        "CITATION RULES:\n"
        "  - Every claim MUST include a 'citations' array with the utterance id(s) "
        "that directly support it (e.g. \"u0012\").\n"
        f"  - Valid ids run from {first_id} to {last_id}. Copy them EXACTLY as written.\n"
        "  - Do not invent ids. Claims citing non-existent ids will be discarded.\n"
        "  - Multiple utterances may support one claim — list all of them.\n\n"
        "CONTENT RULES:\n"
        "  - Extract every piece of clinically relevant information stated in the dialogue.\n"
        "  - Do not invent, infer, or add anything not explicitly present in the dialogue.\n"
        "  - Medications: if the clinician names a specific drug, use that name exactly. "
        "If they describe a drug class or say 'something stronger' without naming it, "
        "write exactly what was said — never infer or supply a drug name not spoken.\n"
        "  - Write each claim as a single, complete, clinical sentence.\n"
        "  - Be thorough: a sparse SOAP note is a patient safety risk.\n\n"
        f"Dialogue:\n{transcript}\n\n"
        "Respond with a single JSON object matching the schema below. "
        "No markdown, no code fences — raw JSON only.\n\n"
        f"Example of the required response shape:\n{example}\n\n"
        f"Schema:\n{json.dumps(SOAP_SCHEMA, indent=2)}\n"
    )
