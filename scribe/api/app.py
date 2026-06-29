"""scribe.api.app — thin FastAPI adapter over Scribe.generateDraft / approveAndExport.

This module is an ADAPTER, not an orchestrator: it translates HTTP
requests into domain calls and domain results into HTTP responses. No
business logic lives here.
"""

from __future__ import annotations

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("scribe.api")

from scribe.api.schemas import (
    ApproveRequest,
    DocumentRefResponse,
    DraftResponse,
    EditDraftRequest,
    GenerateRequest,
    PatientContextDTO,
    SOAPNoteDTO,
    ClaimDTO,
    SpanRefDTO,
    TimeSpanDTO,
    UtteranceDTO,
)
from scribe.app.scribe import Scribe
from scribe.domain.types import (
    Approver,
    Audio,
    Claim,
    EditedDraft,
    PatientContext,
    SOAPNote,
    SpanRef,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only wire real adapters if tests haven't pre-injected a fake scribe.
    if _scribe_instance is None:
        logger.info("[startup] wiring Scribe adapters (Whisper + Ollama + SQLite)…")
        try:
            from scribe.composition import build_scribe
            set_scribe(build_scribe({
                "audio_source": "mic",
                "audio_path": "",
                "draft_store": "sqlite",
                "db_path": "drafts.db",
            }))
            logger.info("[startup] Scribe ready")
        except Exception as exc:
            logger.error("[startup] build_scribe FAILED — %s: %s", type(exc).__name__, exc, exc_info=True)
            logger.warning("[startup] server will start but /drafts/* endpoints will error until fixed")
    else:
        logger.info("[startup] using pre-injected Scribe (test/dev mode)")
    yield


app = FastAPI(title="Ambient Scribe API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level Scribe instance. Tests override via dependency injection.
_scribe_instance: Scribe | None = None


def _get_scribe() -> Scribe:
    if _scribe_instance is None:
        raise RuntimeError("Scribe not initialised — call set_scribe() at startup")
    return _scribe_instance


def set_scribe(scribe: Scribe) -> None:
    """Inject the Scribe instance (used by tests and the server startup)."""
    global _scribe_instance
    _scribe_instance = scribe


# ── domain → DTO helpers ──────────────────────────────────────────────────────

def _note_to_dto(note: SOAPNote) -> SOAPNoteDTO:
    def claim_to_dto(c: Claim) -> ClaimDTO:
        return ClaimDTO(
            text=c.text,
            citations=[
                SpanRefDTO(utterance_id=s.utterance_id, char_span=s.char_span)
                for s in c.citations
            ],
        )

    return SOAPNoteDTO(
        subjective=[claim_to_dto(c) for c in note.subjective],
        objective=[claim_to_dto(c) for c in note.objective],
        assessment=[claim_to_dto(c) for c in note.assessment],
        plan=[claim_to_dto(c) for c in note.plan],
    )


def _draft_to_response(draft) -> DraftResponse:
    return DraftResponse(
        id=draft.id,
        status=draft.status.value,
        ctx=PatientContextDTO(
            patient_ref=draft.ctx.patient_ref,
            encounter_ref=draft.ctx.encounter_ref,
            patient_display=draft.ctx.patient_display,
        ),
        dialogue=[
            UtteranceDTO(
                id=u.id,
                role=u.role.value,
                text=u.text,
                time_span=TimeSpanDTO(start=u.time_span.start, end=u.time_span.end),
                speaker_id=u.speaker_id,
            )
            for u in draft.dialogue.utterances
        ],
        note=_note_to_dto(draft.note),
    )


# ── DTO → domain helpers ──────────────────────────────────────────────────────

def _note_dto_to_domain(dto: SOAPNoteDTO) -> SOAPNote:
    def claim_from_dto(c: ClaimDTO) -> Claim:
        return Claim(
            text=c.text,
            citations=[
                SpanRef(utterance_id=s.utterance_id, char_span=s.char_span)
                for s in c.citations
            ],
        )

    return SOAPNote(
        subjective=[claim_from_dto(c) for c in dto.subjective],
        objective=[claim_from_dto(c) for c in dto.objective],
        assessment=[claim_from_dto(c) for c in dto.assessment],
        plan=[claim_from_dto(c) for c in dto.plan],
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"ok": True, "scribe_ready": _scribe_instance is not None}


@app.post("/audio/upload")
async def upload_audio(file: UploadFile = File(...)) -> dict:
    """Accept a browser file upload, persist to a temp file, return its path."""
    suffix = Path(file.filename or "audio").suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await file.read()
    tmp.write(content)
    tmp.close()
    return {"path": tmp.name, "filename": file.filename, "size": len(content)}


@app.post("/drafts/generate", response_model=DraftResponse)
def generate(req: GenerateRequest, scribe: Scribe = Depends(_get_scribe)) -> DraftResponse:
    audio = Audio(source="file", path=req.audio_path)
    ctx = PatientContext(
        patient_ref=req.patient_ref,
        encounter_ref=req.encounter_ref,
    )
    draft = scribe.generateDraft(audio, ctx)
    return _draft_to_response(draft)


@app.get("/drafts/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: str, scribe: Scribe = Depends(_get_scribe)) -> DraftResponse:
    try:
        draft = scribe.load_draft(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id!r} not found")
    return _draft_to_response(draft)


@app.put("/drafts/{draft_id}", response_model=DraftResponse)
def edit_draft(
    draft_id: str,
    req: EditDraftRequest,
    scribe: Scribe = Depends(_get_scribe),
) -> DraftResponse:
    try:
        draft = scribe.load_draft(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id!r} not found")

    edited = EditedDraft(
        id=draft.id,
        ctx=draft.ctx,
        dialogue=draft.dialogue,
        note=_note_dto_to_domain(req.note),
        provenance=draft.provenance,
    )
    scribe._draft_store.update(edited)
    return _draft_to_response(edited)


@app.post("/drafts/{draft_id}/approve", response_model=DocumentRefResponse)
def approve_draft(
    draft_id: str,
    req: ApproveRequest,
    scribe: Scribe = Depends(_get_scribe),
) -> DocumentRefResponse:
    try:
        draft = scribe.load_draft(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id!r} not found")

    edited = EditedDraft(
        id=draft.id,
        ctx=draft.ctx,
        dialogue=draft.dialogue,
        note=draft.note,
        provenance=draft.provenance,
    )
    approver = Approver(name=req.approver_name, role=req.approver_role)
    doc_ref = scribe.approveAndExport(edited, approver)
    return DocumentRefResponse(resource=doc_ref.resource, json_text=doc_ref.json_text)
