"""NoteGenerator — DEEP module (design.md §3).

Hides prompt construction, constrained-JSON decode, and (Phase 2) span-citation
extraction + validation. Depends on a *thin* ``LLMClient`` — the model swap
lives there, not here, so grounding logic doesn't duplicate across adapters.

Slice 0: plain prompt → LLM → lenient decode → ``SOAPNote`` (no grounding yet).
Phase 2 deepens this to return a ``GroundedNote`` via ``CitationValidator``.
"""

from __future__ import annotations

from scribe.domain.types import Dialogue, SOAPNote
from scribe.notes.decode import parse_soap_note
from scribe.notes.llm.base import LLMClient
from scribe.notes.prompt import SOAP_SCHEMA, build_prompt


class NoteGenerator:
    """Dialogue → SOAPNote (Phase 2: → GroundedNote)."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def generate(self, dialogue: Dialogue) -> SOAPNote:
        if not dialogue.utterances:
            return SOAPNote()  # nothing to summarise
        prompt = build_prompt(dialogue)
        raw = self._llm.complete(prompt, SOAP_SCHEMA)
        return parse_soap_note(raw)

    @property
    def llm_id(self) -> str:
        return self._llm.identifier
