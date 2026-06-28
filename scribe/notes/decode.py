"""Parse LLM JSON output into a SOAPNote. Pure + lenient (Slice 0).

Phase 2 deepens this with constrained-JSON decoding + span-citation
extraction and routes through ``CitationValidator`` to produce a
``GroundedNote``.
"""

from __future__ import annotations

import json
from typing import Any

from scribe.domain.types import Claim, SOAPNote


def parse_soap_note(raw: str | dict[str, Any]) -> SOAPNote:
    """Parse raw model output into a SOAPNote.

    Lenient about: extra whitespace, fenced ```json blocks, missing sections
    (treated as empty), and unknown keys (ignored). Strict about: each section
    being a list of {text: str}.
    """
    data = raw if isinstance(raw, dict) else _extract_json(raw)
    sections = {}
    for key in ("subjective", "objective", "assessment", "plan"):
        sections[key] = _parse_claims(data.get(key, []))
    return SOAPNote(**sections)


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.lstrip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


def _parse_claims(items: Any) -> list[Claim]:
    if not isinstance(items, list):
        return []
    claims = []
    for item in items:
        if isinstance(item, str):
            claims.append(Claim(text=item))
            continue
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                claims.append(Claim(text=text))
    return claims
