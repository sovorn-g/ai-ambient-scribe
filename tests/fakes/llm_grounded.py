"""FakeGroundedLLMClient — canned JSON with valid citations. No model loaded.

Citations reference the utterance IDs in FakeDialogueExtractor._DEFAULT_DIALOGUE
(u0000 = clinician question, u0001 = patient reply), so CitationValidator
accepts every claim without stripping.

Intentionally NOT exported from tests/fakes/__init__.py (that file is frozen).
Import directly: from tests.fakes.llm_grounded import FakeGroundedLLMClient.
"""

from __future__ import annotations

import copy
from typing import Any

from scribe.notes.llm.base import LLMClient


class FakeGroundedLLMClient(LLMClient):
    """Returns canned SOAP JSON with valid citations. Deterministic, no I/O."""

    @property
    def identifier(self) -> str:
        return "fake:llm-grounded"

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(_GROUNDED_CANNED)


# Citations reference FakeDialogueExtractor._DEFAULT_DIALOGUE utterances:
#   u0000: "What brings you in today?"          (CLINICIAN)
#   u0001: "My throat's been sore for three days, especially when I swallow."  (PATIENT)
_GROUNDED_CANNED: dict[str, Any] = {
    "subjective": [
        {
            "text": "Patient reports a sore throat for three days, worse on swallowing.",
            "citations": [{"utterance_id": "u0001"}],
        },
    ],
    "objective": [
        {
            "text": "No objective findings documented in the dialogue.",
            "citations": [{"utterance_id": "u0000"}],
        },
    ],
    "assessment": [
        {
            "text": "Pharyngitis based on patient report.",
            "citations": [{"utterance_id": "u0001"}],
        },
    ],
    "plan": [
        {
            "text": "Follow up if symptoms worsen.",
            "citations": [{"utterance_id": "u0001"}],
        },
    ],
}
