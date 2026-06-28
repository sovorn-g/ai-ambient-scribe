"""Completeness scorers — ROUGE vs ACI-Bench reference notes.

These measure *completeness* (how much of the reference content is present),
NOT faithfulness. Never label these scores as faithfulness — see execute-plan-v2.md §8.
"""
from __future__ import annotations


def score_rouge(hypothesis: str, reference: str) -> dict[str, float]:
    """ROUGE-1/2/L F1 scores (higher is better, range [0, 1]).

    Args:
        hypothesis: generated note text.
        reference:  ACI-Bench reference note text.
    """
    from rouge_score import rouge_scorer as rs
    scorer = rs.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    result = scorer.score(reference, hypothesis)
    return {k: round(v.fmeasure, 4) for k, v in result.items()}


def note_to_text(note) -> str:
    """Flatten a SOAPNote / GroundedNote to a single string for ROUGE scoring."""
    parts: list[str] = []
    for section in ("subjective", "objective", "assessment", "plan"):
        for claim in getattr(note, section, []):
            parts.append(claim.text)
    return " ".join(parts)
