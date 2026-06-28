"""Wiring helpers that build the Scribe graph from fakes — no model loaded."""

from __future__ import annotations

from typing import Any

from scribe.app.drafts import InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.notes.llm.base import LLMClient
from scribe.runtime.model_host import ModelHost
from tests.fakes import FakeAudioSource, FakeDialogueExtractor, FakeLLMClient
from tests.fakes.llm_grounded import FakeGroundedLLMClient


def build_fake_scribe(
    *,
    llm_canned: dict[str, Any] | None = None,
    llm: LLMClient | None = None,
) -> tuple[Scribe, FakeAudioSource, LLMClient]:
    """Build a Scribe wired entirely through fakes. Deterministic, no I/O.

    Phase 2+: defaults to FakeGroundedLLMClient so all claims have valid
    citations and the GroundedNote invariant is satisfied end-to-end.
    Pass ``llm=FakeLLMClient()`` to exercise the ungrounded / empty-note path.
    """
    audio_source = FakeAudioSource()
    resolved_llm: LLMClient = llm or (
        FakeLLMClient(canned=llm_canned) if llm_canned is not None else FakeGroundedLLMClient()
    )
    scribe = Scribe(
        dialogue_extractor=FakeDialogueExtractor(),
        note_generator=NoteGenerator(resolved_llm),
        fhir_exporter=FhirExporter(),
        draft_store=InMemoryDraftStore(),
        model_host=ModelHost(),
    )
    return scribe, audio_source, resolved_llm
