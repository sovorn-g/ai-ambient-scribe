"""End-to-end skeleton test — full path through fakes, no model loaded.

Verifies the Phase-0 acceptance criteria:
  * generateDraft → approve → approveAndExport produces a valid DocumentRef.
  * approve() is the only path from Draft to DocumentRef (no bypass).
  * Every seam interface + domain type is importable.
  * e2e is green with fakes only (no Ollama/mlx needed).
"""

from __future__ import annotations

import json

import pytest

from scribe.app.approval import approve
from scribe.app.drafts import InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.domain import types as T
from scribe.domain.types import (
    Approver,
    Claim,
    DocumentRef,
    Draft,
    EditedDraft,
    GroundedNote,
    PatientContext,
    Role,
    SOAPNote,
    SpanRef,
)
from scribe.dialogue import DialogueExtractor
from scribe.dialogue.aligner import align
from scribe.dialogue.diarizer.base import Diarizer, NullDiarizer
from scribe.dialogue.transcriber.base import Transcriber
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.notes.llm.base import LLMClient
from scribe.notes.prompt import SOAP_SCHEMA, build_prompt
from scribe.runtime.audio import AudioSource, FileAudioSource
from scribe.runtime.model_host import ModelHost
from tests.conftest import build_fake_scribe
from tests.fakes import FakeAudioSource, FakeDialogueExtractor, FakeLLMClient


# ─────────────────────────────────────────────────────────────────────────────
# Importability — every seam interface + every domain type from §1–§3 exists.
# ─────────────────────────────────────────────────────────────────────────────
def test_domain_types_importable():
    for name in [
        "Audio", "TranscriptSeg", "SpeakerTurn", "Utterance", "Dialogue",
        "SpanRef", "Claim", "SOAPNote", "GroundedNote", "PatientContext",
        "Draft", "EditedDraft", "ApprovedNote", "DocumentRef", "EvalReport",
        "Role",
    ]:
        assert hasattr(T, name), f"missing domain type: {name}"


def test_seam_interfaces_importable():
    # Each seam class can be imported and is abstract / instantiable-as-fake.
    assert issubclass(FakeLLMClient, LLMClient)
    assert issubclass(FakeAudioSource, AudioSource)
    assert issubclass(FakeDialogueExtractor, DialogueExtractor)
    assert issubclass(NullDiarizer, Diarizer)
    # FileAudioSource is a real adapter but the seam is real because of the fake too.
    assert issubclass(FileAudioSource, AudioSource)


def test_frozen_scribe_public_surface():
    # The two-method public surface (design.md §3) — FROZEN.
    assert hasattr(Scribe, "generateDraft")
    assert hasattr(Scribe, "approveAndExport")


# ─────────────────────────────────────────────────────────────────────────────
# Invariants encoded as types (design.md §1, §4)
# ─────────────────────────────────────────────────────────────────────────────
def test_groundednote_rejects_ungrounded_claim():
    with pytest.raises(ValueError, match="no citations"):
        GroundedNote(
            subjective=[Claim(text="ungrounded claim", citations=[])],
            objective=[], assessment=[], plan=[],
        )


def test_groundednote_accepts_grounded_claim():
    note = GroundedNote(
        subjective=[Claim(text="ok", citations=[SpanRef(utterance_id="u0000")])],
        objective=[], assessment=[], plan=[],
    )
    assert note.subjective[0].citations


def test_approvednote_cannot_be_constructed_directly():
    with pytest.raises(ValueError, match="approve"):
        ApprovedNote_direct_construction()


def ApprovedNote_direct_construction():
    # The door: no _approval_key → construction must fail.
    from scribe.domain.types import Approver, ApprovedNote, PatientContext, SOAPNote
    from datetime import datetime, timezone
    return ApprovedNote(
        note=SOAPNote(),
        approver=Approver(name="x"),
        approved_at=datetime.now(timezone.utc),
        ctx=PatientContext(patient_ref="p", encounter_ref="e"),
    )


def test_approve_is_the_only_door():
    # approve() succeeds where direct construction fails.
    from scribe.domain.types import Approver, Dialogue, EditedDraft, PatientContext, Provenance, SOAPNote
    edited = EditedDraft(
        id="d1",
        ctx=PatientContext(patient_ref="p", encounter_ref="e"),
        note=SOAPNote(),
        provenance=Provenance(model_id="m", asr_id="a", diarizer_id="d"),
        dialogue=Dialogue(utterances=[]),
    )
    approved = approve(edited, Approver(name="Dr. Test"))
    assert approved.approver.name == "Dr. Test"


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end through fakes — audio → note → approved → DocumentRef.
# ─────────────────────────────────────────────────────────────────────────────
def test_e2e_generate_approve_export():
    scribe, audio_source, _llm = build_fake_scribe()
    ctx = PatientContext(
        patient_ref="primock-patient-01",
        encounter_ref="primock-encounter-01",
        patient_display="PriMock57 Sample Patient",
    )

    # 1. generateDraft — side-effect-free; returns a DRAFT, writes nothing durable.
    audio = audio_source.load()
    draft = scribe.generateDraft(audio, ctx)
    assert isinstance(draft, Draft)
    assert draft.status.value == "DRAFT"
    assert draft.dialogue.utterances  # dialogue came through the fake
    assert draft.note.subjective  # note came through the FakeGroundedLLMClient
    # Phase 2+: every claim is grounded — all claims have ≥1 valid citation.
    assert all(c.citations for c in draft.note.all_claims())

    # 2. Clinician edits (Slice 0: no edits, just round-trip) → EditedDraft.
    edited = EditedDraft(
        id=draft.id,
        ctx=draft.ctx,
        dialogue=draft.dialogue,
        note=draft.note,
        provenance=draft.provenance,
    )

    # 3. approveAndExport — gated; routes through approve().
    doc = scribe.approveAndExport(edited, Approver(name="Dr. Slice Zero", role="clinician"))
    assert isinstance(doc, DocumentRef)
    payload = json.loads(doc.json_text)
    assert payload["resourceType"] == "DocumentReference"
    assert payload["status"] == "current"
    assert payload["docStatus"] == "final"
    assert payload["subject"]["reference"] == "Patient/primock-patient-01"
    assert payload["context"][0]["reference"] == "Encounter/primock-encounter-01"
    # The note text is base64-embedded in the attachment.
    import base64
    body = base64.b64decode(payload["content"][0]["attachment"]["data"]).decode("utf-8")
    assert "SOAP Note" in body
    assert "SUBJECTIVE" in body and "PLAN" in body


def test_e2e_load_draft_round_trip():
    scribe, _audio, _llm = build_fake_scribe()
    ctx = PatientContext(patient_ref="p1", encounter_ref="e1")
    audio = FakeAudioSource().load()
    draft = scribe.generateDraft(audio, ctx)
    assert scribe.load_draft(draft.id).id == draft.id


def test_no_bypass_from_draft_to_documentref():
    # The only writer is approveAndExport, and it requires an Approver.
    scribe, _audio, _llm = build_fake_scribe()
    ctx = PatientContext(patient_ref="p", encounter_ref="e")
    draft = scribe.generateDraft(FakeAudioSource().load(), ctx)

    # Calling approveAndExport without going through EditedDraft→approve is
    # impossible — the facade routes through approve() internally, and there's
    # no other writer on Scribe.
    assert not hasattr(scribe, "export")  # no parallel export method
    assert not hasattr(scribe, "writeFhir")  # no back door
    assert not hasattr(scribe, "saveFhir")  # no back door


# ─────────────────────────────────────────────────────────────────────────────
# Pure-logic units behind the seams (sanity).
# ─────────────────────────────────────────────────────────────────────────────
def test_aligner_passthrough_with_no_turns():
    from scribe.domain.types import TranscriptSeg, TimeSpan
    segs = [
        TranscriptSeg(text="hello", time_span=TimeSpan(start=0, end=1)),
        TranscriptSeg(text="world", time_span=TimeSpan(start=1, end=2)),
        TranscriptSeg(text="", time_span=TimeSpan(start=2, end=3)),  # dropped
    ]
    dialogue = align(segs, turns=[])
    assert [u.text for u in dialogue.utterances] == ["hello", "world"]
    assert all(u.role == Role.UNKNOWN for u in dialogue.utterances)


def test_build_prompt_contains_dialogue_ids():
    from scribe.domain.types import Dialogue, TimeSpan, Utterance
    d = Dialogue(utterances=[
        Utterance(id="u0000", role=Role.CLINICIAN, text="hi", time_span=TimeSpan(start=0, end=1), speaker_id="s1"),
    ])
    prompt = build_prompt(d)
    assert "[u0000]" in prompt
    assert "CLINICIAN" in prompt


def test_decode_handles_fenced_json():
    from scribe.notes.decode import parse_soap_note
    raw = '```json\n{"subjective":[{"text":"ok"}],"objective":[],"assessment":[],"plan":[]}\n```'
    note = parse_soap_note(raw)
    assert note.subjective[0].text == "ok"


def test_fhir_exporter_round_trips():
    from datetime import datetime, timezone
    exporter = FhirExporter()
    from scribe.domain.types import Approver, ApprovedNote, Dialogue, PatientContext, SOAPNote, Provenance, EditedDraft
    edited = EditedDraft(
        id="d", ctx=PatientContext(patient_ref="p", encounter_ref="e"),
        note=SOAPNote(subjective=[Claim(text="x")]),
        provenance=Provenance(model_id="m", asr_id="a", diarizer_id="d"),
        dialogue=Dialogue(utterances=[]),
    )
    approved = approve(edited, Approver(name="Dr. X"))
    doc = exporter.toDocumentReference(approved, edited.ctx)
    parsed = json.loads(doc.json_text)
    assert parsed["resourceType"] == "DocumentReference"
