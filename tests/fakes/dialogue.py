"""FakeDialogueExtractor — returns a fixed Dialogue, no ASR/diarization.

Lets NoteGenerator + FhirExporter tests run in isolation.
"""

from __future__ import annotations

from scribe.domain.types import Audio, Dialogue, Role, TimeSpan, Utterance
from scribe.dialogue import DialogueExtractor  # noqa: F401  (re-exported for type compat)


class FakeDialogueExtractor(DialogueExtractor):
    """Bypasses the real extractor; returns a canned two-utterance Dialogue."""

    def __init__(self, dialogue: Dialogue | None = None) -> None:
        # Intentionally not calling super().__init__ — we override extract().
        self._dialogue = dialogue or _DEFAULT_DIALOGUE

    def extract(self, audio: Audio) -> Dialogue:
        return self._dialogue

    @property
    def transcriber_id(self) -> str:
        return "fake:transcriber"

    @property
    def diarizer_id(self) -> str:
        return "fake:diarizer"


_DEFAULT_DIALOGUE = Dialogue(
    utterances=[
        Utterance(
            id="u0000",
            role=Role.CLINICIAN,
            text="What brings you in today?",
            time_span=TimeSpan(start=0.0, end=2.0),
            speaker_id="spk:clinician",
        ),
        Utterance(
            id="u0001",
            role=Role.PATIENT,
            text="My throat's been sore for three days, especially when I swallow.",
            time_span=TimeSpan(start=2.1, end=6.0),
            speaker_id="spk:patient",
        ),
    ]
)
