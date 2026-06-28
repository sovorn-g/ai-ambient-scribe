"""scribe.api.schemas — DTOs for the FastAPI adapter.

These are transport objects, NOT domain types. They mirror domain types
for serialization but stay decoupled so the API surface can evolve
independently of the domain.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SpanRefDTO(BaseModel):
    utterance_id: str
    char_span: Optional[tuple[int, int]] = None


class ClaimDTO(BaseModel):
    text: str
    citations: list[SpanRefDTO] = Field(default_factory=list)


class SOAPNoteDTO(BaseModel):
    subjective: list[ClaimDTO] = Field(default_factory=list)
    objective: list[ClaimDTO] = Field(default_factory=list)
    assessment: list[ClaimDTO] = Field(default_factory=list)
    plan: list[ClaimDTO] = Field(default_factory=list)


class TimeSpanDTO(BaseModel):
    start: float
    end: float


class UtteranceDTO(BaseModel):
    id: str
    role: str
    text: str
    time_span: TimeSpanDTO
    speaker_id: str


class PatientContextDTO(BaseModel):
    patient_ref: str
    encounter_ref: str
    patient_display: Optional[str] = None


class DraftResponse(BaseModel):
    id: str
    status: str
    ctx: PatientContextDTO
    dialogue: list[UtteranceDTO]
    note: SOAPNoteDTO


class GenerateRequest(BaseModel):
    patient_ref: str
    encounter_ref: str
    audio_path: str


class EditDraftRequest(BaseModel):
    note: SOAPNoteDTO


class ApproveRequest(BaseModel):
    approver_name: str
    approver_role: str = "clinician"


class DocumentRefResponse(BaseModel):
    resource: dict
    json_text: str
