"""AmbientSessionService — Phase 7 live listening state machine.

Owns the nontrivial state of an ambient session: audio accumulation and
finalization into a normal ``Draft`` via the existing ``Scribe.generateDraft``
batch path.

Design rules (plans/phase-7-ambient-listening.md):
  * Finalization calls the existing ``Scribe.generateDraft`` on the FULL captured
    audio, so the final note quality is the same batch pipeline we benchmarked.
    The LLM never sees partial audio — it always waits for the complete recording.
  * The service is an app-layer module (not an API endpoint). The FastAPI
    WebSocket endpoint is a thin adapter over this.
  * Optional background chunk transcription can be added later for long sessions;
    it would not change the final batch path.

Events are plain dicts with a ``type`` key so the endpoint can ``json.dumps``
them directly without coupling to Pydantic DTOs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from scribe.app.scribe import Scribe
from scribe.domain.types import Audio, Draft, PatientContext
from scribe.runtime.live_audio import LiveAudioBuffer

logger = logging.getLogger("scribe.ambient")


@dataclass
class AmbientSession:
    id: str
    ctx: PatientContext
    sample_rate: int
    buffer: LiveAudioBuffer
    state: str = "LISTENING"  # LISTENING | FINALIZING | DONE | CANCELLED
    chunk_count: int = 0


class AmbientSessionService:
    """Registry + lifecycle for ambient listening sessions.

    Live listening = click record, capture the conversation, stop, then feed the
    full captured WAV into the existing normal final pipeline. No provisional
    truth — the final transcript, citations, and note all come from the batch
    dialogue on the complete recording.
    """

    def __init__(self, scribe: Scribe) -> None:
        self._scribe = scribe
        self._sessions: dict[str, AmbientSession] = {}

    # ── session lifecycle ────────────────────────────────────────────────────

    def start_session(
        self,
        ctx: PatientContext,
        sample_rate: int = 16000,
    ) -> AmbientSession:
        session = AmbientSession(
            id=str(uuid4()),
            ctx=ctx,
            sample_rate=sample_rate,
            buffer=LiveAudioBuffer(sample_rate=sample_rate),
        )
        self._sessions[session.id] = session
        logger.info("[ambient] session %s started (sr=%d)", session.id, sample_rate)
        return session

    def get_session(self, session_id: str) -> Optional[AmbientSession]:
        return self._sessions.get(session_id)

    def cancel(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.state = "CANCELLED"
            logger.info("[ambient] session %s cancelled (%.1fs captured)",
                        session_id, session.buffer.duration_seconds())

    async def append_audio(
        self, session_id: str, pcm16: bytes
    ) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None:
            logger.warning("[ambient] append_audio unknown session %s (%d bytes)", session_id, len(pcm16))
            return [{"type": "error", "message": "unknown session"}]
        if session.state != "LISTENING":
            logger.warning("[ambient] append_audio session %s not listening (state=%s, %d bytes)",
                           session_id, session.state, len(pcm16))
            return [{"type": "error", "message": f"session not listening (state={session.state})"}]
        session.buffer.append(pcm16)
        # Log every ~2s of audio to avoid spamming. 16kHz mono PCM16 = 32kB/s.
        session.chunk_count += 1
        if session.chunk_count % 4 == 1:
            logger.info("[ambient] session %s: chunk #%d bytes=%d total=%.1fs",
                        session_id, session.chunk_count, len(pcm16),
                        session.buffer.duration_seconds())
        return [{
            "type": "listening",
            "seconds": round(session.buffer.duration_seconds(), 2),
            "bytes_received": session.buffer.byte_count,
        }]

    async def finalize(self, session_id: str) -> Draft:
        """Stop listening, write the full WAV, run the existing batch pipeline.

        The final LLM feed is always built from the complete recording; partial
        audio is never sent to note generation.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown session {session_id!r}")
        if session.state == "FINALIZING":
            raise RuntimeError("session already finalizing")
        duration = session.buffer.duration_seconds()
        session.state = "FINALIZING"
        logger.info("[ambient] session %s finalizing (%.1fs captured, %d bytes)",
                    session_id, duration, session.buffer.byte_count)
        if duration < 0.2:
            logger.warning("[ambient] session %s finalize on near-empty audio (%.1fs) — "
                           "transcript/note will likely be empty", session_id, duration)
        try:
            wav_path = session.buffer.write_wav()
            logger.info("[ambient] session %s wrote WAV %s", session_id, wav_path)
            audio = Audio(source="stream", path=wav_path, sample_rate=session.sample_rate)
            # Run the (CPU/GPU-bound) batch pipeline off the event loop.
            draft = await asyncio.to_thread(self._scribe.generateDraft, audio, session.ctx)
            session.state = "DONE"
            dialogue = getattr(draft, "dialogue", None)
            n_utts = len(getattr(dialogue, "utterances", []) or []) if dialogue is not None else 0
            logger.info("[ambient] session %s → draft %s utterances=%d", session_id, draft.id, n_utts)
            return draft
        finally:
            # Keep the session record so the caller can read final state, but
            # drop the heavy audio buffer.
            session.buffer = LiveAudioBuffer(sample_rate=session.sample_rate)
