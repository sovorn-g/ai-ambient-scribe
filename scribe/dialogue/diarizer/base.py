"""Diarizer [seam] — speaker-attribution adapter interface.

HYPOTHETICAL seam (design.md §5): one adapter (sherpa-onnx) in scope for Phase 1.
Slice 0 uses ``NullDiarizer`` so the DialogueExtractor seam stands up without
the flakiest component.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from scribe.domain.types import Audio, SpeakerTurn


class Diarizer(ABC):
    """Segment audio into speaker turns."""

    @abstractmethod
    def diarize(self, audio: Audio) -> list[SpeakerTurn]:
        raise NotImplementedError

    @property
    def identifier(self) -> str:
        return self.__class__.__name__


class NullDiarizer(Diarizer):
    """Slice-0 placeholder: no diarization. Returns no speaker turns."""

    def diarize(self, audio: Audio) -> list[SpeakerTurn]:
        return []

    @property
    def identifier(self) -> str:
        return "null"
