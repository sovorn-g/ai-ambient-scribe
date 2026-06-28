"""Parse LLM JSON output into a SOAPNote. Pure + lenient (Slice 0).

Phase 2 deepens this with constrained-JSON decoding + span-citation
extraction and routes through ``CitationValidator`` to produce a
``GroundedNote``.
"""

from __future__ import annotations

import json
from typing import Any

from scribe.domain.types import Claim, SOAPNote, SpanRef


def parse_soap_note(raw: str | dict[str, Any]) -> SOAPNote:
    """Parse raw model output into a SOAPNote.

    Lenient about: extra whitespace, fenced ```json blocks, missing sections
    (treated as empty), unknown keys (ignored), and the common LLM failure of
    wrapping the response inside a schema-mimicking ``{"type": "object",
    "properties": {...}}`` wrapper (unwrapped automatically). Strict about:
    each section being a list of {text: str}.
    """
    data = raw if isinstance(raw, dict) else _extract_json(raw)
    data = _unwrap_schema_echo(data)
    sections = {}
    for key in ("subjective", "objective", "assessment", "plan"):
        sections[key] = _parse_claims(data.get(key, []))
    return SOAPNote(**sections)


def _unwrap_schema_echo(data: dict[str, Any]) -> dict[str, Any]:
    """If the LLM echoed the schema wrapper, unwrap to the instance under 'properties'.

    Some LLMs respond to "match this schema" by producing
    ``{"type": "object", "properties": {<actual soap note>}, ...}``
    instead of an instance. Detect and unwrap that pattern.
    """
    if (
        isinstance(data, dict)
        and data.get("type") == "object"
        and isinstance(data.get("properties"), dict)
        and any(k in data["properties"] for k in ("subjective", "objective", "assessment", "plan"))
    ):
        return data["properties"]
    return data


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
                citations = _parse_citations(item.get("citations"))
                claims.append(Claim(text=text, citations=citations))
    return claims


def _parse_citations(raw: Any) -> list[SpanRef]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        uid = item.get("utterance_id")
        if not isinstance(uid, str) or not uid.strip():
            continue
        char_span: tuple[int, int] | None = None
        cs = item.get("char_span")
        if isinstance(cs, (list, tuple)) and len(cs) == 2:
            try:
                char_span = (int(cs[0]), int(cs[1]))
            except (TypeError, ValueError):
                pass
        refs.append(SpanRef(utterance_id=uid, char_span=char_span))
    return refs
