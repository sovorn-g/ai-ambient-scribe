"""eval.bakeoff — bake-off report container.

A ``BakeoffReport`` holds one ``EvalReport`` per model in the registry. WER/DER
are model-invariant (ASR + diarization are locked axes per execute-plan-v2.md
§5) and therefore identical across per-model reports; the renderer surfaces
them once in a "locked axes" section. Grounding + completeness are the real
per-model comparison.

This type lives in ``eval/`` (not in the frozen ``scribe.domain.types``) because
it's an eval-side concern: it composes the existing ``EvalReport`` rather than
extending the frozen domain vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass

from scribe.domain.types import EvalReport
from eval.models import ModelRegistry


@dataclass
class BakeoffReport:
    """Per-model ``EvalReport``s plus the registry that produced them."""

    registry: ModelRegistry
    per_model: dict[str, EvalReport]
