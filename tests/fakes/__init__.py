"""Shared fakes — FROZEN (phase-0 plan rule 5).

These are the second adapters that make several seams real (DraftStore, etc.)
and let the whole Scribe graph run end-to-end with no model loaded, no mic,
no file. Downstream phases MUST NOT break these.
"""

from tests.fakes.audio import FakeAudioSource
from tests.fakes.dialogue import FakeDialogueExtractor
from tests.fakes.llm import FakeLLMClient

__all__ = ["FakeAudioSource", "FakeDialogueExtractor", "FakeLLMClient"]
