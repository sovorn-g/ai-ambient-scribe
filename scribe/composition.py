"""composition.py — the wiring root (design.md §6).

The ONLY place real adapters are constructed and injected. Everything else
accepts dependencies; it doesn't create them. That's what makes the graph
testable through fakes.

Per-seam factory stubs (rule 2 of phase-0 plan): each later phase fills in
the BODY of one factory without touching the call sequence in ``build_scribe``.
The call sequence is FROZEN; the bodies deepen.
"""

from __future__ import annotations

from typing import Any

from scribe.app.drafts import DraftStore, InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.dialogue import DialogueExtractor
from scribe.dialogue.diarizer.base import Diarizer, NullDiarizer
from scribe.dialogue.transcriber.base import Transcriber
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.notes.llm.base import LLMClient
from scribe.runtime.audio import AudioSource, FileAudioSource
from scribe.runtime.model_host import ModelHost


# ── Per-seam factory stubs. Bodies deepen per phase; signatures stay. ─────────
def _build_transcriber(cfg: Any) -> Transcriber:
    """Phase 0: mlx-whisper. (Phase 1+: optional Parakeet swap — not yet.)"""
    from scribe.dialogue.transcriber.mlx_whisper import MlxWhisperTranscriber

    return MlxWhisperTranscriber(cfg.get("transcriber", {}))


def _build_diarizer(cfg: Any) -> Diarizer:
    """Phase 0: NullDiarizer. Phase 1: sherpa-onnx when ``cfg.diarizer.model_path``
    is set; otherwise fall back to NullDiarizer (keeps the phase-0 e2e path green
    when no diarizer is configured)."""
    dcfg = cfg.get("diarizer", {}) or {}
    model_path = dcfg.get("model_path")
    if not model_path:
        return NullDiarizer()
    from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer

    return SherpaOnnxDiarizer(
        model_path=model_path,
        num_threads=int(dcfg.get("num_threads", 1)),
        num_clusters=int(dcfg.get("num_clusters", -1)),
        threshold=float(dcfg.get("threshold", 0.5)),
        sample_rate=int(dcfg.get("sample_rate", 16000)),
    )


def _build_llm(cfg: Any) -> LLMClient:
    """Phase 0: Ollama/Qwen2.5-7B. Phase 4 may add a model_id param for bake-off."""
    from scribe.notes.llm.ollama import OllamaLLMClient

    return OllamaLLMClient(cfg.get("llm", {}))


def _build_note_generator(cfg: Any) -> NoteGenerator:
    """Phase 0: plain prompt, no grounding. Phase 2 deepens with CitationValidator."""
    return NoteGenerator(_build_llm(cfg))


def _build_audio_source(cfg: Any) -> AudioSource:
    """Phase 0/eval: FileAudioSource. Phase 5 fills mic/stream."""
    return FileAudioSource(cfg["audio_path"])


def _build_draft_store(cfg: Any) -> DraftStore:
    """Phase 0: in-memory. Phase 5 fills sqlite."""
    return InMemoryDraftStore()


def _build_model_host(cfg: Any) -> ModelHost:
    """Phase 0: trivial. Phase 4 deepens (multi-model residency for bake-off)."""
    return ModelHost(cfg.get("model_host", {}))


def _build_dialogue_extractor(cfg: Any) -> DialogueExtractor:
    return DialogueExtractor(
        transcriber=_build_transcriber(cfg),
        diarizer=_build_diarizer(cfg),
    )


def _build_fhir_exporter(cfg: Any) -> FhirExporter:
    return FhirExporter()


# ── build_scribe — call sequence FROZEN ───────────────────────────────────────
def build_scribe(cfg: dict[str, Any]) -> Scribe:
    """Wire the real-adapter graph. Tests build the graph with fakes instead."""
    model_host = _build_model_host(cfg)
    dialogue_extractor = _build_dialogue_extractor(cfg)
    note_generator = _build_note_generator(cfg)
    fhir_exporter = _build_fhir_exporter(cfg)
    draft_store = _build_draft_store(cfg)
    audio_source = _build_audio_source(cfg)

    scribe = Scribe(
        dialogue_extractor=dialogue_extractor,
        note_generator=note_generator,
        fhir_exporter=fhir_exporter,
        draft_store=draft_store,
        model_host=model_host,
    )
    # Expose the audio source on the facade so the thin CLI adapter can reach it
    # without re-resolving cfg. (Adapters may do this; deeper callers go through
    # generateDraft.)
    scribe._audio_source = audio_source  # type: ignore[attr-defined]
    return scribe
