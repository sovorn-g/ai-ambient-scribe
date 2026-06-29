"""eval.models — the bake-off registry (design.md §7 row 4, execute-plan-v2.md §3).

A thin, pure data module: lists the three Ollama model tags we compare plus
per-model prompt notes. No I/O, no model loaded. The harness iterates this
registry; ``OllamaLLMClient`` accepts the ``ollama_tag`` as its ``model_id``.

ASR + diarization are **locked** — only the note-LLM varies (execute-plan-v2.md
§5). The three tags are chosen so the comparison answers an interesting
question *and* swapping is free via Ollama:

  * ``qwen2.5:7b-instruct-q4_K_M``   — general instruct, 7B (baseline).
  * ``medgemma:4b``                  — medical fine-tune, 4B (the question).
  * ``llama3.1:8b-instruct-q4_K_M``  — general instruct, 8B (size control).

Memory budgets are conservative q4 footprints on Apple Silicon; the
``ModelHost`` evicts the previous resident before loading the next so the
bake-off runs sequentially within 16GB.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelSpec:
    """One entry in the bake-off registry."""

    model_id: str           # short, stable id used as the per-model row key
    ollama_tag: str         # the string passed to OllamaLLMClient(model_id=…)
    memory_gb: float        # conservative resident footprint for budget checks
    prompt_notes: str = ""  # per-model prompting tweaks (empty = default prompt)


@dataclass
class ModelRegistry:
    """Ordered list of ``ModelSpec``s the bake-off iterates over."""

    models: list[ModelSpec] = field(default_factory=list)

    def get(self, model_id: str) -> ModelSpec | None:
        for m in self.models:
            if m.model_id == model_id:
                return m
        return None

    @property
    def total_memory_gb(self) -> float:
        return sum(m.memory_gb for m in self.models)


DEFAULT_REGISTRY = ModelRegistry(
    models=[
        ModelSpec(
            model_id="qwen2.5-7b",
            ollama_tag="qwen2.5:7b-instruct-q4_K_M",
            memory_gb=5.0,
            prompt_notes="Baseline general-instruct 7B. Default SOAP prompt.",
        ),
        ModelSpec(
            model_id="medgemma-4b",
            ollama_tag="medgemma:4b",
            memory_gb=3.0,
            prompt_notes=(
                "Medical fine-tune. Use the default prompt; the model is "
                "already conditioned for clinical text."
            ),
        ),
        ModelSpec(
            model_id="llama3.1-8b",
            ollama_tag="llama3.1:8b-instruct-q4_K_M",
            memory_gb=6.0,
            prompt_notes="General-instruct 8B. Size-control arm.",
        ),
    ]
)
