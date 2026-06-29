"""Aligner — pure function mapping transcript segments + speaker turns to utterances.

DEEP, pure, no seam (design.md §5). When diarizer turns and word-level
timestamps are both available, segments are split at speaker-change
boundaries word-by-word so that a single Whisper segment containing two
speakers produces two correctly-attributed utterances instead of one
misattributed one. Without word timings (or with NullDiarizer), the old
max-overlap assignment is used as a fallback.
"""

from __future__ import annotations

from scribe.domain.types import (
    Dialogue, Role, SpeakerTurn, TimeSpan, TranscriptSeg, Utterance, WordTiming,
)

UNKNOWN_SPEAKER = "spk:unknown"


def _stable_utterance_id(index: int) -> str:
    return f"u{index:04d}"


def align(
    segments: list[TranscriptSeg],
    turns: list[SpeakerTurn],
    *,
    base_role: Role = Role.UNKNOWN,
) -> Dialogue:
    """Align transcript segments to speaker turns.

    - ``turns`` empty (NullDiarizer): each non-empty segment → UNKNOWN role,
      ``spk:unknown`` speaker.
    - ``turns`` present + word timings available: segments are split at
      speaker-change boundaries using per-word timestamps.
    - ``turns`` present, no word timings: max-overlap assignment per segment.
    - Empty-text segments are dropped in all branches.
    """
    utterances: list[Utterance] = []
    kept = 0

    for seg in segments:
        if not seg.text:
            continue

        if turns and seg.word_timings:
            sub = _split_by_speaker(seg, turns)
        elif turns:
            best = _best_overlap_turn(seg.time_span, turns)
            speaker_id = best.speaker_id if best else UNKNOWN_SPEAKER
            sub = [(seg.text, seg.time_span, speaker_id)]
        else:
            sub = [(seg.text, seg.time_span, UNKNOWN_SPEAKER)]

        for text, span, speaker_id in sub:
            utterances.append(
                Utterance(
                    id=_stable_utterance_id(kept),
                    role=base_role,
                    text=text,
                    time_span=span,
                    speaker_id=speaker_id,
                )
            )
            kept += 1

    return Dialogue(utterances=utterances)


def _split_by_speaker(
    seg: TranscriptSeg, turns: list[SpeakerTurn]
) -> list[tuple[str, TimeSpan, str]]:
    """Split a segment into sub-segments at speaker-change boundaries.

    Each word's midpoint is matched to the best diarizer turn. Consecutive
    words with the same speaker are grouped into one sub-segment.
    """
    groups: list[tuple[str, TimeSpan, str]] = []
    current_words: list[WordTiming] = []
    current_speaker: str | None = None

    for word in seg.word_timings:
        best = _best_overlap_turn(word.time_span, turns)
        speaker = best.speaker_id if best else UNKNOWN_SPEAKER

        if current_speaker is None:
            current_speaker = speaker

        if speaker != current_speaker:
            _flush(current_words, current_speaker, groups)
            current_words = [word]
            current_speaker = speaker
        else:
            current_words.append(word)

    _flush(current_words, current_speaker or UNKNOWN_SPEAKER, groups)

    # Fallback: if splitting produced nothing (e.g. all words empty), keep original
    if not groups:
        best = _best_overlap_turn(seg.time_span, turns)
        speaker_id = best.speaker_id if best else UNKNOWN_SPEAKER
        return [(seg.text, seg.time_span, speaker_id)]

    return groups


def _flush(
    words: list[WordTiming], speaker: str, out: list[tuple[str, TimeSpan, str]]
) -> None:
    if not words:
        return
    text = " ".join(w.word for w in words).strip()
    if not text:
        return
    span = TimeSpan(start=words[0].time_span.start, end=words[-1].time_span.end)
    out.append((text, span, speaker))


def _best_overlap_turn(span: TimeSpan, turns: list[SpeakerTurn]) -> SpeakerTurn | None:
    """Return the turn whose time_span overlaps ``span`` the most.

    Falls back to nearest turn by midpoint when no turn overlaps — catches
    short fillers ("Um", "No", "Bye") that fall in diarization gaps.
    """
    best: SpeakerTurn | None = None
    best_overlap = 0.0
    for turn in turns:
        ov = max(0.0, min(span.end, turn.time_span.end) - max(span.start, turn.time_span.start))
        if ov > best_overlap:
            best, best_overlap = turn, ov
    if best is not None:
        return best
    mid = (span.start + span.end) / 2.0
    return min(turns, key=lambda t: abs((t.time_span.start + t.time_span.end) / 2.0 - mid))
