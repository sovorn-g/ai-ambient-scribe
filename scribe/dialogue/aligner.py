"""Aligner — pure function mapping transcript segments + speaker turns to utterances.

DEEP, pure, no seam (design.md §5). Slice 0: passthrough — no turns yet, so
each segment becomes one UNKNOWN-role utterance. Phase 1 deepens this to
align segments to turns by time overlap.
"""

from __future__ import annotations

from scribe.domain.types import Dialogue, Role, SpeakerTurn, TimeSpan, TranscriptSeg, Utterance


def _stable_utterance_id(index: int) -> str:
    return f"u{index:04d}"


def align(
    segments: list[TranscriptSeg],
    turns: list[SpeakerTurn],
    *,
    base_role: Role = Role.UNKNOWN,
) -> Dialogue:
    """Align transcript segments to speaker turns.

    Slice-0 behavior: ``turns`` is empty (NullDiarizer), so each segment becomes
    one utterance with ``role=UNKNOWN`` and a synthetic ``speaker_id``. The
    Phase-1 deepening (turn-aware alignment + role labelling) replaces only the
    body of this function; the signature stays.
    """
    if not turns:
        utterances = [
            Utterance(
                id=_stable_utterance_id(i),
                role=base_role,
                text=seg.text,
                time_span=seg.time_span,
                speaker_id="spk:unknown",
            )
            for i, seg in enumerate(segments)
            if seg.text  # drop empty segments
        ]
        return Dialogue(utterances=utterances)

    # Phase-1 alignment sketch (kept simple, intentional). Turns are present;
    # assign each segment the speaker of the turn whose time_span overlaps most.
    utterances: list[Utterance] = []
    for i, seg in enumerate(segments):
        best_turn = _best_overlap_turn(seg.time_span, turns)
        utterances.append(
            Utterance(
                id=_stable_utterance_id(i),
                role=base_role,  # Phase 1's RoleLabeller refines this.
                text=seg.text,
                time_span=seg.time_span,
                speaker_id=best_turn.speaker_id if best_turn else "spk:unknown",
            )
        )
    return Dialogue(utterances=utterances)


def _best_overlap_turn(span: TimeSpan, turns: list[SpeakerTurn]) -> SpeakerTurn | None:
    best, best_overlap = None, 0.0
    for turn in turns:
        ov = max(0.0, min(span.end, turn.time_span.end) - max(span.start, turn.time_span.start))
        if ov > best_overlap:
            best, best_overlap = turn, ov
    return best
