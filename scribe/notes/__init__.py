"""NoteGenerator — DEEP module (design.md §3).

Hides prompt construction, constrained-JSON decode, and span-citation
extraction + validation. Depends on a *thin* ``LLMClient`` — the model swap
lives there, not here, so grounding logic doesn't duplicate across adapters.

Phase 2: returns ``GroundedNote`` via ``CitationValidator``.
Policy: ungrounded claims are dropped (not re-asked); the ``GroundedNote``
invariant is enforced structurally so no ungrounded content can reach a Draft.
"""

from __future__ import annotations

import logging

from scribe.domain.types import Dialogue, GroundedNote
from scribe.notes.citations import CitationValidator, Violations
from scribe.notes.decode import parse_soap_note
from scribe.notes.llm.base import LLMClient
from scribe.notes.prompt import SOAP_SCHEMA, build_prompt

_log = logging.getLogger(__name__)


class NoteGenerator:
    """Dialogue → GroundedNote."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._validator = CitationValidator()

    def generate(self, dialogue: Dialogue) -> GroundedNote:
        if not dialogue.utterances:
            return GroundedNote()  # nothing to summarise
        prompt = build_prompt(dialogue)
        raw = self._llm.complete(prompt, SOAP_SCHEMA)
        soap_note = parse_soap_note(raw)
        result = self._validator.validate(soap_note, dialogue)
        if isinstance(result, Violations):
            _log.warning(
                "NoteGenerator: all claims were ungrounded — returning empty note. "
                "Violations: %s",
                [(v.section, v.claim_text[:40]) for v in result.items],
            )
            return GroundedNote()
        return result

    @property
    def llm_id(self) -> str:
        return self._llm.identifier
