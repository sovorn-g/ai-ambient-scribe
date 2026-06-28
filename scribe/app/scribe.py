"""Scribe — the public surface (DEEP, design.md §3). FROZEN after Phase 0.

Two methods, behind which sits the entire product. CLI, Next.js, and (partly)
eval are its adapters — two+ callers, so this seam is REAL.

  generateDraft(audio, ctx) -> Draft           # no side effects; the only writer is below
  approveAndExport(edited, approver) -> DocumentRef   # GATED — see scribe.app.approval

The approval invariant is structural: ``approveAndExport`` accepts an
``EditedDraft`` and routes through ``approve()`` — the sole constructor of
``ApprovedNote``. No bypass exists.
"""

from __future__ import annotations

from uuid import uuid4

from scribe.app.approval import approve
from scribe.app.drafts import DraftStore
from scribe.domain.types import (
    Approver,
    Audio,
    DocumentRef,
    Draft,
    EditedDraft,
    PatientContext,
    Provenance,
)
from scribe.dialogue import DialogueExtractor
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.runtime.model_host import ModelHost


class Scribe:
    """The facade callers depend on. Composition root injects every dependency."""

    def __init__(
        self,
        dialogue_extractor: DialogueExtractor,
        note_generator: NoteGenerator,
        fhir_exporter: FhirExporter,
        draft_store: DraftStore,
        model_host: ModelHost | None = None,
    ) -> None:
        self._dialogue_extractor = dialogue_extractor
        self._note_generator = note_generator
        self._fhir_exporter = fhir_exporter
        self._draft_store = draft_store
        self._model_host = model_host or ModelHost()

    def generateDraft(self, audio: Audio, ctx: PatientContext) -> Draft:
        """Audio → Draft. Side-effect-free: returns the Draft, writes nothing."""
        # Best-effort residency hint; Slice 0 ModelHost is a no-op.
        self._model_host.ensure_resident(self._note_generator.llm_id)

        dialogue = self._dialogue_extractor.extract(audio)
        note = self._note_generator.generate(dialogue)
        provenance = Provenance(
            model_id=self._note_generator.llm_id,
            asr_id=self._dialogue_extractor.transcriber_id,
            diarizer_id=self._dialogue_extractor.diarizer_id,
        )
        draft = Draft(
            id=str(uuid4()),
            ctx=ctx,
            dialogue=dialogue,
            note=note,
            provenance=provenance,
        )
        self._draft_store.save(draft)
        return draft

    def approveAndExport(self, edited: EditedDraft, approver: Approver) -> DocumentRef:
        """EditedDraft + Approver → validated FHIR DocumentReference.

        The only writer in the system, and it is gated: it constructs an
        ``ApprovedNote`` via ``approve()`` (the sole door) before exporting.
        """
        approved = approve(edited, approver)
        return self._fhir_exporter.toDocumentReference(approved, edited.ctx)

    def load_draft(self, draft_id: str) -> Draft:
        """Adapter helper: pull a draft back from the store."""
        return self._draft_store.get(draft_id)
