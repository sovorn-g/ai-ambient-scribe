"""Aligner — pure function mapping transcript segments + speaker turns to utterances.

DEEP, pure, no seam (design.md §5). Phase 1: each transcript segment is
assigned the ``speaker_id`` of the turn whose ``time_span`` overlaps it most
(max temporal overlap). Segments that fall in a gap (no overlap) get
``spk:unknown``. Empty-text segments are dropped in both branches. Utterance
ids are stable zero-padded indices over the *kept* segments.

The signature stays; Phase 1 only deepened the body.
"""

from __future__ import annotations

from scribe.domain.types import Dialogue, Role, SpeakerTurn, TimeSpan, TranscriptSeg, Utterance

UNKNOWN_SPEAKER = "spk:unknown"


def _stable_utterance_id(index: int) -> str:
    return f"u{index:04d}"


def align(
    segments: list[TranscriptSeg],
    turns: list[SpeakerTurn],
    *,
    base_role: Role = Role.UNKNOWN,
) -> Dialogue:
    """Align transcript segments to speaker turns by max temporal overlap.

    - ``turns`` empty (NullDiarizer): each non-empty segment → UNKNOWN role,
      ``spk:unknown`` speaker (Slice-0 behaviour preserved).
    - ``turns`` present: each non-empty segment → ``base_role`` role and the
      speaker_id of the turn with the most overlap; gaps → ``spk:unknown``.
    - Empty-text segments are dropped in both branches.
    """
    utterances: list[Utterance] = []
    for i, seg in enumerate(segments):
        if not seg.text:
            continue  # drop empty segments consistently
        best_turn = _best_overlap_turn(seg.time_span, turns) if turns else None
        speaker_id = best_turn.speaker_id if best_turn is not None else UNKNOWN_SPEAKER
        utterances.append(
            Utterance(
                id=_stable_utterance_id(i),
                role=base_role,
                text=seg.text,
                time_span=seg.time_span,
                speaker_id=speaker_id,
            )
        )
    return Dialogue(utterances=utterances)


def _best_overlap_turn(span: TimeSpan, turns: list[SpeakerTurn]) -> SpeakerTurn | None:
    """Return the turn whose time_span overlaps ``span`` the most.

    Ties broken by first occurrence (stable — deterministic across runs).
    Returns ``None`` when no turn overlaps.
    """
    best: SpeakerTurn | None = None
    best_overlap = 0.0
    for turn in turns:
        ov = max(0.0, min(span.end, turn.time_span.end) - max(span.start, turn.time_span.start))
        if ov > best_overlap:
            best, best_overlap = turn, ov
    return best
