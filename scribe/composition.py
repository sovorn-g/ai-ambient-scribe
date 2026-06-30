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
        segmentation_model_path=dcfg.get("segmentation_model_path"),
        num_threads=int(dcfg.get("num_threads", 1)),
        num_clusters=int(dcfg.get("num_clusters", -1)),
        threshold=float(dcfg.get("threshold", 0.5)),
        sample_rate=int(dcfg.get("sample_rate", 16000)),
        min_duration_on=float(dcfg.get("min_duration_on", 0.3)),
        min_duration_off=float(dcfg.get("min_duration_off", 0.5)),
    )


def _build_llm(cfg: Any) -> LLMClient:
    """Phase 0: Ollama/Qwen2.5-7B. Phase 4 may add a model_id param for bake-off."""
    from scribe.notes.llm.ollama import OllamaLLMClient

    return OllamaLLMClient(cfg.get("llm", {}))


def _build_note_generator(cfg: Any) -> NoteGenerator:
    """Phase 0: plain prompt, no grounding. Phase 2 deepens with CitationValidator."""
    return NoteGenerator(_build_llm(cfg))


def _build_audio_source(cfg: Any) -> AudioSource:
    """Phase 0/eval: FileAudioSource. Phase 5: mic/stream when audio_source='mic'."""
    source_type = cfg.get("audio_source", "file")
    if source_type == "mic":
        from scribe.runtime.audio import MicStreamAudioSource
        return MicStreamAudioSource(cfg.get("audio_path", ""))
    return FileAudioSource(cfg["audio_path"])


def _build_draft_store(cfg: Any) -> DraftStore:
    """Phase 0: in-memory. Phase 5: sqlite when draft_store='sqlite'."""
    store_type = cfg.get("draft_store", "memory")
    if store_type == "sqlite":
        from scribe.app.drafts import SqliteDraftStore
        return SqliteDraftStore(cfg.get("db_path", "drafts.db"))
    return InMemoryDraftStore()


def _build_model_host(cfg: Any) -> ModelHost:
    """Phase 4: deepened with injected loader/evictor callbacks + memory budget.

    cfg.model_host may carry:
      * ``loader`` / ``evictor``: callables (model_tag) -> None. If absent,
        the host is a no-op tracker (CI/test path).
      * ``memory_budget_gb``: advisory budget, default 16.0.

    Real Ollama wiring (e.g. ``ollama pull`` / unload) is injected here; the
    bake-off harness calls ``ensure_resident`` per model so the previous
    resident is evicted before the next loads.
    """
    mcfg = cfg.get("model_host", {}) or {}
    return ModelHost(
        mcfg,
        loader=mcfg.get("loader"),
        evictor=mcfg.get("evictor"),
        memory_budget_gb=float(mcfg.get("memory_budget_gb", 16.0)),
    )


def _build_dialogue_extractor(cfg: Any) -> DialogueExtractor:
    return DialogueExtractor(
        transcriber=_build_transcriber(cfg),
        diarizer=_build_diarizer(cfg),
    )


def _build_fhir_exporter(cfg: Any) -> FhirExporter:
    return FhirExporter()


def build_ambient_service(cfg: Any, scribe: "Scribe") -> "AmbientSessionService":
    """Wire the AmbientSessionService with the existing Scribe.

    Live listening = capture → stop → ``Scribe.generateDraft`` on the full WAV.
    No preview transcriber is wired; the service does not emit partial
    transcripts. (Background chunk transcription can be added later for long
    sessions without changing the final batch path.)
    """
    from scribe.app.ambient import AmbientSessionService
    return AmbientSessionService(scribe=scribe)


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
