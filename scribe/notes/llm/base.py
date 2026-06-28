"""LLMClient [SEAM] — the one real model seam (design.md §3, §5).

The bake-off (Phase 4) and the local-privacy story both pivot here. Note
generation logic (prompt construction, decode, grounding) lives in
``NoteGenerator`` and is shared across every model — only the raw completion
varies through this seam.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Complete a prompt against a JSON schema, returning parsed JSON."""

    @abstractmethod
    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def identifier(self) -> str:
        return self.__class__.__name__
