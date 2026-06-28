"""RoleLabeller — pure heuristic mapping speaker_id → Role.

DEEP, pure, no seam (design.md §5). Slice 0: returns ``Role.UNKNOWN`` for
everyone (no diarization yet). Phase 1 deepens with a heuristic (e.g. first
speaker → CLINICIAN, other → PATIENT) plus manual-correction fallback.
"""

from __future__ import annotations

from scribe.domain.types import Dialogue, Role


def label_roles(dialogue: Dialogue) -> Dialogue:
    """Slice 0: no relabelling — every utterance keeps its existing role."""
    return dialogue


def guess_role(speaker_id: str) -> Role:
    """Phase-1 hook placeholder. Slice 0 always returns UNKNOWN."""
    return Role.UNKNOWN
