"""WER scorer — pure function wrapping jiwer."""
from __future__ import annotations


def score_wer(hypothesis: str, reference: str) -> float:
    """Word Error Rate (lower is better; range [0, ∞)).

    Args:
        hypothesis: ASR output (model prediction).
        reference:  Ground-truth transcript.
    """
    if not reference.strip():
        return 0.0 if not hypothesis.strip() else 1.0
    from jiwer import wer
    return float(wer(reference, hypothesis))
