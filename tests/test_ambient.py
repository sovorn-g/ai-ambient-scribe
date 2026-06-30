"""tests/test_ambient.py — AmbientSessionService + WebSocket endpoint (fakes).

Verifies the live-listening state machine without any model:
  * session lifecycle (start / append / cancel / finalize)
  * finalize calls the existing Scribe.generateDraft batch path on the full WAV
  * WebSocket protocol: start → binary chunks → stop → draft_ready

No mlx-whisper, no Ollama, no mic. The fake Scribe ignores audio content and
returns the canned grounded draft.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scribe.api.app import app, set_ambient_service, set_scribe
from scribe.app.ambient import AmbientSessionService
from scribe.domain.types import PatientContext
from tests.conftest import build_fake_scribe


# ── fakes ─────────────────────────────────────────────────────────────────────


def _build_service() -> AmbientSessionService:
    scribe, _, _ = build_fake_scribe()
    set_scribe(scribe)
    return AmbientSessionService(scribe=scribe)


def _pcm16_chunk(seconds: float, sample_rate: int = 16000) -> bytes:
    """N seconds of silent PCM16 mono (zeros)."""
    n = int(seconds * sample_rate)
    return b"\x00\x00" * n


# ── LiveAudioBuffer unit tests ────────────────────────────────────────────────


def test_buffer_append_and_duration():
    from scribe.runtime.live_audio import LiveAudioBuffer

    buf = LiveAudioBuffer(sample_rate=16000)
    assert buf.duration_seconds() == 0.0
    buf.append(_pcm16_chunk(1.0))
    assert buf.duration_seconds() == pytest.approx(1.0, abs=0.001)
    buf.append(_pcm16_chunk(2.0))
    assert buf.duration_seconds() == pytest.approx(3.0, abs=0.001)
    assert buf.sample_count == 16000 * 3


def test_buffer_append_drops_odd_byte():
    from scribe.runtime.live_audio import LiveAudioBuffer

    buf = LiveAudioBuffer(sample_rate=16000)
    buf.append(b"\x00\x00\x00")  # 1.5 samples → drop trailing byte
    assert buf.byte_count == 2


def test_buffer_write_wav_is_valid(tmp_path: Path):
    from scribe.runtime.live_audio import LiveAudioBuffer

    buf = LiveAudioBuffer(sample_rate=16000)
    buf.append(_pcm16_chunk(0.5))
    path = buf.write_wav(tmp_path / "out.wav")
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        assert w.getsampwidth() == 2
        assert w.getnframes() == 8000


def test_buffer_extract_window_clamps():
    from scribe.runtime.live_audio import LiveAudioBuffer

    buf = LiveAudioBuffer(sample_rate=16000)
    buf.append(_pcm16_chunk(3.0))
    # window beyond buffer end is clamped
    win = buf.extract_window(2.0, 10.0)
    assert len(win) == 16000 * 2  # only 1s available after 2.0s
    # window before start is empty
    assert buf.extract_window(5.0, 8.0) == b""


# ── AmbientSessionService lifecycle ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_session_returns_id():
    service = _build_service()
    ctx = PatientContext(patient_ref="p-1", encounter_ref="e-1")
    session = service.start_session(ctx)
    assert session.id
    assert session.state == "LISTENING"
    assert service.get_session(session.id) is session


@pytest.mark.asyncio
async def test_append_audio_emits_listening_event():
    service = _build_service()
    session = service.start_session(PatientContext(patient_ref="p", encounter_ref="e"))
    events = await service.append_audio(session.id, _pcm16_chunk(1.0))
    assert events[0]["type"] == "listening"
    assert events[0]["seconds"] == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_append_audio_unknown_session_errors():
    service = _build_service()
    events = await service.append_audio("nope", _pcm16_chunk(0.1))
    assert events[0]["type"] == "error"


@pytest.mark.asyncio
async def test_finalize_returns_draft_via_batch_path():
    service = _build_service()
    session = service.start_session(PatientContext(patient_ref="p", encounter_ref="e"))
    await service.append_audio(session.id, _pcm16_chunk(2.0))
    draft = await service.finalize(session.id)
    assert draft.status.value == "DRAFT"
    assert draft.id
    # The fake Scribe returns a grounded 2-utterance dialogue.
    assert len(draft.dialogue.utterances) == 2
    assert session.state == "DONE"


@pytest.mark.asyncio
async def test_finalize_unknown_session_raises():
    service = _build_service()
    with pytest.raises(KeyError):
        await service.finalize("nope")


@pytest.mark.asyncio
async def test_cancel_cleans_session():
    service = _build_service()
    session = service.start_session(PatientContext(patient_ref="p", encounter_ref="e"))
    service.cancel(session.id)
    assert service.get_session(session.id) is None


@pytest.mark.asyncio
async def test_append_after_cancel_errors():
    service = _build_service()
    session = service.start_session(PatientContext(patient_ref="p", encounter_ref="e"))
    service.cancel(session.id)
    events = await service.append_audio(session.id, _pcm16_chunk(0.1))
    assert events[0]["type"] == "error"


# ── WebSocket endpoint integration ─────────────────────────────────────────────


@pytest.fixture()
def ws_client():
    service = _build_service()
    set_ambient_service(service)
    with TestClient(app) as c:
        yield c


def _ws_connect(client: TestClient):
    return client.websocket_connect("/ambient/ws")


def test_ws_start_emits_session_started(ws_client: TestClient):
    with _ws_connect(ws_client) as ws:
        ws.send_text(json.dumps({"type": "start", "patient_ref": "p", "encounter_ref": "e"}))
        msg = ws.receive_json()
        assert msg["type"] == "session_started"
        assert "session_id" in msg


def test_ws_audio_before_start_errors(ws_client: TestClient):
    with _ws_connect(ws_client) as ws:
        ws.send_bytes(_pcm16_chunk(0.1))
        msg = ws.receive_json()
        assert msg["type"] == "error"


def test_ws_full_flow_to_draft_ready(ws_client: TestClient):
    with _ws_connect(ws_client) as ws:
        ws.send_text(json.dumps({"type": "start", "patient_ref": "p", "encounter_ref": "e"}))
        ws.receive_json()  # session_started
        ws.send_bytes(_pcm16_chunk(1.0))
        listening = ws.receive_json()
        assert listening["type"] == "listening"
        ws.send_text(json.dumps({"type": "stop"}))
        finalizing = ws.receive_json()
        assert finalizing["type"] == "finalizing"
        draft_msg = ws.receive_json()
        assert draft_msg["type"] == "draft_ready"
        assert draft_msg["draft"]["status"] == "DRAFT"
        assert len(draft_msg["draft"]["dialogue"]) == 2


def test_ws_cancel_emits_cancelled(ws_client: TestClient):
    with _ws_connect(ws_client) as ws:
        ws.send_text(json.dumps({"type": "start", "patient_ref": "p", "encounter_ref": "e"}))
        ws.receive_json()
        ws.send_text(json.dumps({"type": "cancel"}))
        msg = ws.receive_json()
        assert msg["type"] == "cancelled"


def test_ws_unknown_command_errors(ws_client: TestClient):
    with _ws_connect(ws_client) as ws:
        ws.send_text(json.dumps({"type": "bogus"}))
        msg = ws.receive_json()
        assert msg["type"] == "error"
