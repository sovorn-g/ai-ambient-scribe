"""Ollama LLMClient — real adapter, parameterized by Ollama model tag.

Phase 4 uses this single adapter for the note-LLM bake-off: each ``ModelSpec``
in ``eval/models.py`` is swapped in by constructing ``OllamaLLMClient(model_id=
spec.ollama_tag)``. The grounding + prompt logic lives in ``scribe/notes`` and
is shared across every model — only the *completion* varies through this seam,
which is exactly the locality rule from design.md §5.

Heavy import (ollama python client) is deferred to ``__init__`` so importing
this module never requires the optional dep.
"""

from __future__ import annotations

import json
from typing import Any

from scribe.notes.llm.base import LLMClient


class OllamaLLMClient(LLMClient):
    """Talks to a local Ollama server (OpenAI-compatible / chat)."""

    def __init__(self, cfg: Any | None = None, model_id: str | None = None) -> None:
        self.cfg = cfg or {}
        if isinstance(self.cfg, dict):
            self.model_id = model_id or self.cfg.get("model_id", "qwen2.5:7b-instruct-q4_K_M")
            self.host = self.cfg.get("host", "http://localhost:11434")
            self.temperature = float(self.cfg.get("temperature", 0.0))
        else:
            self.model_id = model_id or "qwen2.5:7b-instruct-q4_K_M"
            self.host = "http://localhost:11434"
            self.temperature = 0.0

    @property
    def identifier(self) -> str:
        return f"ollama:{self.model_id}"

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            import ollama  # type: ignore
        except ImportError as e:  # pragma: no cover - needs ollama installed
            raise RuntimeError(
                "ollama python client is not installed. Install with: pip install -e .[phase0]"
            ) from e

        client = ollama.Client(host=self.host)
        # Ask for JSON; Slice 0 doesn't enforce the schema server-side — decode.py
        # parses leniently. Phase 2 will pass `format=schema` for constrained output.
        response = client.chat(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": self.temperature},
        )
        content = response["message"]["content"]
        return json.loads(content)
