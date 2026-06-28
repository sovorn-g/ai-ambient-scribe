"""scribe.domain.types — domain vocabulary that crosses every seam.

FROZEN after Phase 0. Downstream phases add depth behind fixed interfaces;
they do NOT change these types. See design.md §1.

Two invariants are encoded as *types*, not checks:
  * ``GroundedNote``  — a SOAPNote where every Claim has >=1 valid SpanRef.
  * ``ApprovedNote``  — constructable ONLY via ``scribe.app.approval.approve()``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class Role(str, Enum):
    """Speaker role attributed to an utterance."""

    CLINICIAN = "CLINICIAN"
    PATIENT = "PATIENT"
    UNKNOWN = "UNKNOWN"


class DraftStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


# ─────────────────────────────────────────────────────────────────────────────
# Time + audio primitives
# ─────────────────────────────────────────────────────────────────────────────
class TimeSpan(BaseModel):
    """Half-open [start, end) in seconds from audio start."""

    start: float
    end: float

    @model_validator(mode="after")
    def _check_order(self) -> "TimeSpan":
        if self.end < self.start:
            raise ValueError("TimeSpan end must be >= start")
        return self


class WordTiming(BaseModel):
    word: str
    time_span: TimeSpan


class Audio(BaseModel):
    """Handle to PCM samples.

    Slice 0: ``FileAudioSource`` populates ``path``; ``samples`` is optional and
    loaded lazily by transcribers that need raw PCM. Keeping this a thin handle
    (not a big buffer) means the seam stays cheap to fake.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str  # "file" | "mic" | "stream" | "fake"
    path: Optional[str] = None
    sample_rate: int = 16000
    channels: int = 1
    # Optional in-memory samples (numpy array / bytes). Held as Any to avoid a
    # hard numpy dep on the type; adapters that need it may set it.
    samples: Optional[Any] = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal pipeline artifacts (DialogueExtractor internals)
# ─────────────────────────────────────────────────────────────────────────────
class TranscriptSeg(BaseModel):
    """Raw ASR output segment."""

    text: str
    time_span: TimeSpan
    word_timings: list[WordTiming] = Field(default_factory=list)


class SpeakerTurn(BaseModel):
    """Diarizer output: a contiguous span attributed to one speaker id."""

    speaker_id: str
    time_span: TimeSpan


class Utterance(BaseModel):
    """An attributed, role-labelled piece of dialogue.

    This is the unit the NoteGenerator consumes; its ``id`` is what SpanRef
    citations point at.
    """

    id: str
    role: Role
    text: str
    time_span: TimeSpan
    speaker_id: str


class Dialogue(BaseModel):
    """Ordered list of utterances — the DialogueExtractor output."""

    utterances: list[Utterance] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Note-level types
# ─────────────────────────────────────────────────────────────────────────────
class SpanRef(BaseModel):
    """A citation pointing into a Dialogue utterance.

    ``char_span`` is an optional [start, end) into ``utterance.text``; when
    omitted, the citation references the whole utterance.
    """

    utterance_id: str
    char_span: Optional[tuple[int, int]] = None


class Claim(BaseModel):
    """A single SOAP assertion plus the transcript spans that ground it."""

    text: str
    citations: list[SpanRef] = Field(default_factory=list)


class SOAPNote(BaseModel):
    """A SOAP note. Slice 0 returns this; Phase 2 returns ``GroundedNote``."""

    subjective: list[Claim] = Field(default_factory=list)
    objective: list[Claim] = Field(default_factory=list)
    assessment: list[Claim] = Field(default_factory=list)
    plan: list[Claim] = Field(default_factory=list)

    def all_claims(self) -> list[Claim]:
        return [*self.subjective, *self.objective, *self.assessment, *self.plan]


class GroundedNote(SOAPNote):
    """A SOAPNote where every Claim has >=1 valid SpanRef.

    Constructing one with an ungrounded Claim raises — the invariant is
    structural, not a runtime check someone can forget.
    """

    @model_validator(mode="after")
    def _every_claim_grounded(self) -> "GroundedNote":
        for section in (self.subjective, self.objective, self.assessment, self.plan):
            for claim in section:
                if not claim.citations:
                    raise ValueError(
                        f"GroundedNote invariant violated: claim has no citations: {claim.text!r}"
                    )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Context, drafts, approval gate
# ─────────────────────────────────────────────────────────────────────────────
class PatientContext(BaseModel):
    """Patient + Encounter references. Slice 0: hardcoded. Phase 5+: Synthea."""

    patient_ref: str  # FHIR Patient id
    encounter_ref: str  # FHIR Encounter id
    patient_display: Optional[str] = None


class Approver(BaseModel):
    """The human signing off on a draft."""

    name: str
    role: str = "clinician"


class Provenance(BaseModel):
    """Where the draft came from — captured for audit / FHIR provenance."""

    model_id: str
    asr_id: str
    diarizer_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Draft(BaseModel):
    """Output of ``Scribe.generateDraft``. Status=DRAFT; nothing written."""

    id: str
    ctx: PatientContext
    dialogue: Dialogue
    note: SOAPNote  # SOAPNote @ Slice 0; GroundedNote @ Phase 2
    provenance: Provenance
    status: DraftStatus = DraftStatus.DRAFT


class EditedDraft(BaseModel):
    """A Draft after human edits. Still DRAFT — approval is a separate door."""

    id: str
    ctx: PatientContext
    dialogue: Dialogue
    note: SOAPNote
    provenance: Provenance
    status: DraftStatus = DraftStatus.DRAFT


# ─────────────────────────────────────────────────────────────────────────────
# ApprovedNote — the ONLY door from Draft to DocumentRef (design.md §4)
# ─────────────────────────────────────────────────────────────────────────────
# Module-private sentinel. approval.py imports it; nothing else should.
_APPROVAL_KEY = object()


class ApprovedNote(BaseModel):
    """A note that has passed the human approval gate.

    Cannot be constructed directly — construction requires the module-private
    ``_APPROVAL_KEY`` sentinel, which only ``scribe.app.approval.approve()``
    holds. This makes the human-in-the-loop guarantee *structural*: there is no
    path from ``Draft`` to ``DocumentRef`` that skips approval.
    """

    model_config = ConfigDict(extra="allow")

    note: SOAPNote
    approver: Approver
    approved_at: datetime
    ctx: PatientContext

    @model_validator(mode="after")
    def _enforce_door(self) -> "ApprovedNote":
        extra: dict[str, Any] = getattr(self, "__pydantic_extra__", None) or {}
        if extra.get("_approval_key") is not _APPROVAL_KEY:
            raise ValueError(
                "ApprovedNote cannot be constructed directly. "
                "Use scribe.app.approval.approve(edited, approver)."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# FHIR + eval outputs
# ─────────────────────────────────────────────────────────────────────────────
class DocumentRef(BaseModel):
    """A validated FHIR R5 DocumentReference, serialized to a Python dict.

    We keep this as a thin wrapper over the raw FHIR resource dict so the
    ``Scribe`` public surface doesn't leak ``fhir.resources`` types to its
    adapters (CLI / Next.js). Adapters that need the raw resource can read
    ``resource``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    resource: dict[str, Any]
    json_text: str  # serialized form, ready to write to disk


class EvalReport(BaseModel):
    """Metrics table — per component, per model. Phase 3 fills the body."""

    metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
