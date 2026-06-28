"""FakeLLMClient — canned JSON completion, no model loaded.

Large adapter, tiny implementation: lets every NoteGenerator path (prompt,
decode, Phase-2 CitationValidator) run deterministically in CI.
"""

from __future__ import annotations

from typing import Any

from scribe.notes.llm.base import LLMClient


class FakeLLMClient(LLMClient):
    """Returns a canned SOAP JSON, ignoring the prompt."""

    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.canned = canned or _DEFAULT_CANNED
        self.calls: list[str] = []

    @property
    def identifier(self) -> str:
        return "fake:llm"

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(prompt)
        return _deep_copy(self.canned)


def _deep_copy(obj: Any) -> Any:
    import copy

    return copy.deepcopy(obj)


_DEFAULT_CANNED: dict[str, Any] = {
    "subjective": [
        {"text": "Patient reports a sore throat for three days, worse on swallowing."},
        {"text": "No fever, no cough reported."},
    ],
    "objective": [
        {"text": "Tonsils erythematous with no exudate; no cervical lymphadenopathy."},
    ],
    "assessment": [
        {"text": "Viral pharyngitis — symptoms consistent with the dialogue."},
    ],
    "plan": [
        {"text": "Rest and fluids; analgesia as needed."},
        {"text": "Return if symptoms worsen or persist beyond seven days."},
    ],
}
