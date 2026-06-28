"""EvalHarness — drives Scribe over a Dataset and collects metrics.

This is the second caller over the Scribe seam (CLI + eval, design.md §5).
It uses ONLY the public Scribe.generateDraft interface — no monkeypatching.
If a metric ever requires reaching past the interface, the seam is wrong
(design.md §6).
"""
from __future__ import annotations

from scribe.app.scribe import Scribe
from scribe.domain.types import EvalReport, PatientContext
from eval.datasets.base import Dataset
from eval.metrics.completeness import note_to_text, score_rouge
from eval.metrics.wer import score_wer


class EvalHarness:
    """Runs a Scribe over every item in a Dataset and returns an EvalReport."""

    def __init__(self, scribe: Scribe, ctx: PatientContext) -> None:
        self._scribe = scribe
        self._ctx = ctx

    def run(self, dataset: Dataset) -> EvalReport:
        wer_scores: list[float] = []
        der_scores: list[float] = []
        rouge1: list[float] = []
        rouge2: list[float] = []
        rougeL: list[float] = []

        for item in dataset.items():
            draft = self._scribe.generateDraft(item.audio, self._ctx)

            if item.reference_transcript is not None:
                hyp = _dialogue_to_text(draft.dialogue)
                wer_scores.append(score_wer(hyp, item.reference_transcript))

            if item.reference_rttm is not None:
                try:
                    from eval.metrics.der import (
                        dialogue_to_annotation,
                        rttm_to_annotation,
                        score_der,
                    )
                    ref_ann = rttm_to_annotation(item.reference_rttm, uri=item.item_id)
                    hyp_ann = dialogue_to_annotation(draft.dialogue, uri=item.item_id)
                    der_scores.append(score_der(ref_ann, hyp_ann))
                except Exception:
                    pass

            if item.reference_note is not None:
                hyp_text = note_to_text(draft.note)
                scores = score_rouge(hyp_text, item.reference_note)
                rouge1.append(scores["rouge1"])
                rouge2.append(scores["rouge2"])
                rougeL.append(scores["rougeL"])

        metrics: dict[str, dict[str, float]] = {}
        if wer_scores:
            metrics["asr"] = {"wer": _mean(wer_scores)}
        if der_scores:
            metrics["diarization"] = {"der": _mean(der_scores)}
        if rouge1:
            metrics["completeness"] = {
                "rouge1": _mean(rouge1),
                "rouge2": _mean(rouge2),
                "rougeL": _mean(rougeL),
            }

        return EvalReport(metrics=metrics)


def _dialogue_to_text(dialogue) -> str:
    return " ".join(u.text for u in dialogue.utterances)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4)
