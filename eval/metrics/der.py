"""DER scorer — pure functions wrapping pyannote.metrics.

All functions accept pyannote.core.Annotation objects so the scorer is
dependency-injectable and trivially testable with toy fixtures.
"""
from __future__ import annotations


def score_der(reference, hypothesis) -> float:
    """Diarization Error Rate (lower is better).

    Args:
        reference:  pyannote.core.Annotation — ground-truth speaker turns.
        hypothesis: pyannote.core.Annotation — predicted speaker turns.
    """
    from pyannote.metrics.diarization import DiarizationErrorRate
    metric = DiarizationErrorRate()
    return float(metric(reference, hypothesis))


def rttm_to_annotation(rttm_text: str, uri: str = ""):
    """Parse RTTM text into a pyannote.core.Annotation.

    RTTM line format:
      SPEAKER <file_id> 1 <start> <duration> <NA> <NA> <speaker_id> <NA> <NA>
    """
    from pyannote.core import Annotation, Segment
    ann = Annotation(uri=uri)
    for line in rttm_text.strip().splitlines():
        parts = line.split()
        if len(parts) < 9 or parts[0] != "SPEAKER":
            continue
        start = float(parts[3])
        duration = float(parts[4])
        speaker = parts[7]
        ann[Segment(start, start + duration)] = speaker
    return ann


def dialogue_to_annotation(dialogue, uri: str = ""):
    """Convert a Dialogue to a pyannote Annotation for DER scoring."""
    from pyannote.core import Annotation, Segment
    ann = Annotation(uri=uri)
    for utt in dialogue.utterances:
        seg = Segment(utt.time_span.start, utt.time_span.end)
        ann[seg] = utt.speaker_id
    return ann
