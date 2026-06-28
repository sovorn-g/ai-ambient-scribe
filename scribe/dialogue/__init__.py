"""DialogueExtractor — DEEP module (design.md §3).

Composes Transcriber + Diarizer + Aligner + RoleLabeller behind one method.
The caller wants *attributed dialogue*, never a raw transcript — so ASR,
diarization, alignment, and role-labelling are internal seams, not top-level
modules.
"""

from __future__ import annotations

from scribe.domain.types import Audio, Dialogue
from scribe.dialogue.aligner import align
from scribe.dialogue.diarizer.base import Diarizer, NullDiarizer
from scribe.dialogue.roles import label_roles
from scribe.dialogue.transcriber.base import Transcriber


class DialogueExtractor:
    """Audio → attributed Dialogue."""

    def __init__(self, transcriber: Transcriber, diarizer: Diarizer | None = None) -> None:
        self._transcriber = transcriber
        self._diarizer = diarizer or NullDiarizer()

    def extract(self, audio: Audio) -> Dialogue:
        segments = self._transcriber.transcribe(audio)
        turns = self._diarizer.diarize(audio)
        dialogue = align(segments, turns)
        return label_roles(dialogue)

    @property
    def transcriber_id(self) -> str:
        return self._transcriber.identifier

    @property
    def diarizer_id(self) -> str:
        return self._diarizer.identifier
