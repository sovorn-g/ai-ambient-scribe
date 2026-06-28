"""mlx-whisper transcriber — thin real adapter (large-v3-turbo).

Heavy import (mlx_whisper) is deferred to ``__init__`` so the module imports
without the optional dep installed; fakes and tests never pay for it.
"""

from __future__ import annotations

from typing import Any

from scribe.domain.types import Audio, TimeSpan, TranscriptSeg, WordTiming
from scribe.dialogue.transcriber.base import Transcriber


class MlxWhisperTranscriber(Transcriber):
    """Real ASR adapter backed by mlx-whisper (Apple-Silicon native)."""

    def __init__(self, cfg: Any | None = None, model_id: str = "large-v3-turbo") -> None:
        self.cfg = cfg or {}
        self.model_id = self.cfg.get("model_id", model_id) if isinstance(self.cfg, dict) else model_id

    @property
    def identifier(self) -> str:
        return f"mlx-whisper:{self.model_id}"

    def transcribe(self, audio: Audio) -> list[TranscriptSeg]:
        if audio.path is None:
            raise ValueError("MlxWhisperTranscriber requires audio.path")
        try:
            import mlx_whisper  # type: ignore
        except ImportError as e:  # pragma: no cover - needs mlx-whisper installed
            raise RuntimeError(
                "mlx-whisper is not installed. Install with: pip install -e .[phase0]"
            ) from e

        result = mlx_whisper.transcribe(
            audio.path,
            path_or_hf_repo=self.model_id,
            word_timestamps=True,
        )
        segments: list[TranscriptSeg] = []
        for seg in result.get("segments", []):
            word_timings = [
                WordTiming(word=w["word"].strip(), time_span=TimeSpan(start=w["start"], end=w["end"]))
                for w in seg.get("words", []) or []
            ]
            segments.append(
                TranscriptSeg(
                    text=seg["text"].strip(),
                    time_span=TimeSpan(start=float(seg["start"]), end=float(seg["end"])),
                    word_timings=word_timings,
                )
            )
        return segments
