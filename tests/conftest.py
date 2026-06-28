"""Wiring helpers that build the Scribe graph from fakes — no model loaded."""

from __future__ import annotations

from typing import Any

from scribe.app.drafts import InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.runtime.model_host import ModelHost
from tests.fakes import FakeAudioSource, FakeDialogueExtractor, FakeLLMClient


def build_fake_scribe(
    *,
    llm_canned: dict[str, Any] | None = None,
) -> tuple[Scribe, FakeAudioSource, FakeLLMClient]:
    """Build a Scribe wired entirely through fakes. Deterministic, no I/O."""
    audio_source = FakeAudioSource()
    llm = FakeLLMClient(canned=llm_canned)
    scribe = Scribe(
        dialogue_extractor=FakeDialogueExtractor(),
        note_generator=NoteGenerator(llm),
        fhir_exporter=FhirExporter(),
        draft_store=InMemoryDraftStore(),
        model_host=ModelHost(),
    )
    return scribe, audio_source, llm
