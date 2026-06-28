"""FakeAudioSource — fixed Audio handle, no mic, no file."""

from __future__ import annotations

from scribe.domain.types import Audio
from scribe.runtime.audio import AudioSource


class FakeAudioSource(AudioSource):
    def __init__(self, audio: Audio | None = None) -> None:
        self._audio = audio or Audio(source="fake", path=None)

    def load(self) -> Audio:
        return self._audio

    @property
    def identifier(self) -> str:
        return "fake:audio"
