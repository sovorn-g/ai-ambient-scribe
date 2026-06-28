"""Transcriber [seam] — ASR adapter interface.

HYPOTHETICAL seam (design.md §5): one adapter (mlx-whisper) in scope. The
interface is real so Phase 1+ can deepen it, but we don't gold-plate
swappability theatre.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from scribe.domain.types import Audio, TranscriptSeg


class Transcriber(ABC):
    """Transcribe audio into ordered transcript segments."""

    @abstractmethod
    def transcribe(self, audio: Audio) -> list[TranscriptSeg]:
        raise NotImplementedError

    @property
    def identifier(self) -> str:
        return self.__class__.__name__
