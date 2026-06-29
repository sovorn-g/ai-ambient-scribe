"""AudioSource [SEAM] — design.md §5. REAL seam (file + mic/stream + fake).

This *is* the plan's "input source ≠ processing mode": the pipeline always
processes a live ambient audio stream; the demo feeds a recording *into that
live pipeline*.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from scribe.domain.types import Audio


class AudioSource(ABC):
    """Produce an ``Audio`` handle for the pipeline."""

    @abstractmethod
    def load(self) -> Audio:
        raise NotImplementedError

    @property
    def identifier(self) -> str:
        return self.__class__.__name__


class FileAudioSource(AudioSource):
    """Slice-0 / eval adapter: load a wav from disk."""

    def __init__(self, path: str) -> None:
        self.path = str(path)
        if not Path(self.path).exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")

    def load(self) -> Audio:
        return Audio(source="file", path=self.path)

    @property
    def identifier(self) -> str:
        return f"file:{self.path}"


class MicStreamAudioSource(AudioSource):
    """Demo adapter: feeds a recording into the live pipeline as if it were mic input.

    Phase 5a stub: wraps a file path as a stream source. In a real deployment
    this would capture from the system microphone in real time.
    """

    def __init__(self, path: str = "") -> None:
        self.path = str(path)

    def load(self) -> Audio:
        return Audio(source="stream", path=self.path if self.path else None)

    @property
    def identifier(self) -> str:
        return f"mic:{self.path}"
