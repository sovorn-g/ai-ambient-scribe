"""RoleLabeller — pure heuristic mapping speaker_id → Role (design.md §5).

DEEP, pure, no seam. Phase 1 heuristic:
  1. Collect distinct real speaker ids (excluding ``spk:unknown``) in
     first-appearance order.
  2. One real speaker  → that speaker is CLINICIAN.
  3. Two real speakers → first by first-appearance is CLINICIAN, second is
     PATIENT. Tiebreak when first appearances share a timestamp: the speaker
     who asks more questions (``?`` count) is CLINICIAN — clinicians ask the
     questions in a consult.
  4. 3+ real speakers → first = CLINICIAN, second = PATIENT, rest = UNKNOWN.
  5. ``spk:unknown`` (segments that fell in a diarization gap) stays UNKNOWN.

Manual correction hook (the fallback per the plan): ``label_roles`` accepts a
``role_map`` that overrides the heuristic for the listed speakers; the
standalone ``apply_role_map`` is the Phase-5 UI entry point for fixing a
mis-attributed speaker without re-running the heuristic.
"""

from __future__ import annotations

from scribe.dialogue.aligner import UNKNOWN_SPEAKER
from scribe.domain.types import Dialogue, Role


def label_roles(dialogue: Dialogue, *, role_map: dict[str, Role] | None = None) -> Dialogue:
    """Apply the role heuristic, then override with ``role_map`` if given.

    ``role_map`` entries win over the heuristic for the listed speakers;
    un-listed speakers keep their heuristic-derived role.
    """
    heuristic = _infer_role_map(dialogue)
    merged = {**heuristic, **(role_map or {})}
    return _apply_role_map(dialogue, merged)


def apply_role_map(dialogue: Dialogue, role_map: dict[str, Role]) -> Dialogue:
    """Standalone correction hook — replace roles for the listed speakers only.

    Does NOT run the heuristic. Use this when the clinician fixes one
    mis-attributed speaker label in the UI; use ``label_roles(role_map=...)``
    when you want heuristic + partial override in one pass.
    """
    return _apply_role_map(dialogue, role_map)


def guess_role(speaker_id: str, *, role_map: dict[str, Role] | None = None) -> Role:
    """Lookup a speaker's role from a map (manual correction context).

    Returns ``Role.UNKNOWN`` for unmapped speakers — this is a lookup helper,
    not the heuristic; use ``label_roles`` to derive roles from a dialogue.
    """
    if role_map and speaker_id in role_map:
        return role_map[speaker_id]
    return Role.UNKNOWN


# ── internals ─────────────────────────────────────────────────────────────────
def _infer_role_map(dialogue: Dialogue) -> dict[str, Role]:
    real_speakers: list[str] = []
    seen: set[str] = set()
    first_start: dict[str, float] = {}
    question_count: dict[str, int] = {}

    for u in dialogue.utterances:
        sid = u.speaker_id
        if sid is None or sid == UNKNOWN_SPEAKER:
            continue
        if sid not in seen:
            seen.add(sid)
            real_speakers.append(sid)
            first_start[sid] = u.time_span.start
        question_count[sid] = question_count.get(sid, 0) + u.text.count("?")

    role_map: dict[str, Role] = {UNKNOWN_SPEAKER: Role.UNKNOWN}

    if not real_speakers:
        return role_map
    if len(real_speakers) == 1:
        role_map[real_speakers[0]] = Role.CLINICIAN
        return role_map

    first, second = real_speakers[0], real_speakers[1]
    # Tiebreak: same first-appearance timestamp → question-density wins.
    if first_start[first] == first_start[second]:
        if question_count.get(second, 0) > question_count.get(first, 0):
            first, second = second, first
    role_map[first] = Role.CLINICIAN
    role_map[second] = Role.PATIENT
    for extra in real_speakers[2:]:
        role_map[extra] = Role.UNKNOWN
    return role_map


def _apply_role_map(dialogue: Dialogue, role_map: dict[str, Role]) -> Dialogue:
    new_utterances = []
    for u in dialogue.utterances:
        new_role = role_map.get(u.speaker_id)
        if new_role is not None and new_role != u.role:
            new_utterances.append(u.model_copy(update={"role": new_role}))
        else:
            new_utterances.append(u)
    return Dialogue(utterances=new_utterances)
