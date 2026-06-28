"""Phase 3a — eval harness unit tests.

Scorers are pure functions; tested directly on tiny fixtures (no model loaded).
Harness is tested through a fake Dataset + the existing build_fake_scribe helper.
"""
from __future__ import annotations

import pytest

from scribe.domain.types import (
    Audio,
    Claim,
    Dialogue,
    EvalReport,
    PatientContext,
    Role,
    SOAPNote,
    TimeSpan,
    Utterance,
)
from eval.datasets.base import Dataset, DatasetItem
from eval.metrics.completeness import note_to_text, score_rouge
from eval.metrics.wer import score_wer
from eval.harness import EvalHarness
from eval.report import render_report


# ── WER ───────────────────────────────────────────────────────────────────────

def test_wer_perfect_match():
    assert score_wer("hello world", "hello world") == pytest.approx(0.0)


def test_wer_one_substitution():
    # "earth" replaces "world" — one word wrong out of two → 50% WER
    assert score_wer("hello earth", "hello world") == pytest.approx(0.5)


def test_wer_both_empty():
    assert score_wer("", "") == pytest.approx(0.0)


def test_wer_hypothesis_empty():
    # every reference word is a deletion → WER ≥ 1.0
    assert score_wer("", "hello world") >= 1.0


def test_wer_high_error():
    assert score_wer("foo bar baz", "hello world test") > 0.9


# ── ROUGE ─────────────────────────────────────────────────────────────────────

def test_rouge_perfect():
    scores = score_rouge("patient reports headache", "patient reports headache")
    assert scores["rouge1"] == pytest.approx(1.0)
    assert scores["rougeL"] == pytest.approx(1.0)


def test_rouge_partial():
    scores = score_rouge(
        "patient reports headache",
        "patient reports severe headache for two days",
    )
    assert 0.0 < scores["rouge1"] < 1.0


def test_rouge_no_overlap():
    scores = score_rouge("xyz abc def", "patient reports headache")
    assert scores["rouge1"] == pytest.approx(0.0)


def test_rouge_keys():
    scores = score_rouge("a b c", "a b c d")
    assert set(scores.keys()) == {"rouge1", "rouge2", "rougeL"}


# ── DER ───────────────────────────────────────────────────────────────────────

def test_der_perfect():
    from pyannote.core import Annotation, Segment
    from eval.metrics.der import score_der

    ref = Annotation()
    ref[Segment(0, 5)] = "A"
    ref[Segment(5, 10)] = "B"

    hyp = Annotation()
    hyp[Segment(0, 5)] = "A"
    hyp[Segment(5, 10)] = "B"

    assert score_der(ref, hyp) == pytest.approx(0.0)


def test_der_nonzero_when_speaker_wrong():
    from pyannote.core import Annotation, Segment
    from eval.metrics.der import score_der

    ref = Annotation()
    ref[Segment(0, 5)] = "A"
    ref[Segment(5, 10)] = "B"

    hyp = Annotation()
    hyp[Segment(0, 10)] = "A"  # one speaker for everything

    assert score_der(ref, hyp) > 0.0


def test_rttm_to_annotation_parses_one_segment():
    from eval.metrics.der import rttm_to_annotation

    rttm = "SPEAKER test 1 0.0 5.0 <NA> <NA> SPEAKER_A <NA> <NA>"
    ann = rttm_to_annotation(rttm, uri="test")
    assert len(ann) == 1


def test_rttm_to_annotation_skips_invalid_lines():
    from eval.metrics.der import rttm_to_annotation

    rttm = "\n# comment\nSPEAKER test 1 0.0 3.0 <NA> <NA> A <NA> <NA>\n"
    ann = rttm_to_annotation(rttm)
    assert len(ann) == 1


def test_dialogue_to_annotation():
    from eval.metrics.der import dialogue_to_annotation

    dialogue = Dialogue(utterances=[
        Utterance(id="u0", role=Role.CLINICIAN, text="hi",
                  time_span=TimeSpan(start=0.0, end=2.0), speaker_id="spk0"),
        Utterance(id="u1", role=Role.PATIENT, text="hello",
                  time_span=TimeSpan(start=2.1, end=5.0), speaker_id="spk1"),
    ])
    ann = dialogue_to_annotation(dialogue)
    assert len(ann) == 2


# ── note_to_text ──────────────────────────────────────────────────────────────

def test_note_to_text_flattens_all_sections():
    note = SOAPNote(
        subjective=[Claim(text="sore throat")],
        objective=[Claim(text="no fever")],
        assessment=[Claim(text="viral pharyngitis")],
        plan=[Claim(text="rest and fluids")],
    )
    text = note_to_text(note)
    assert "sore throat" in text
    assert "no fever" in text
    assert "viral pharyngitis" in text
    assert "rest and fluids" in text


def test_note_to_text_empty_note():
    assert note_to_text(SOAPNote()) == ""


# ── Dataset seam ──────────────────────────────────────────────────────────────

def test_primock57_returns_empty_for_missing_dir():
    from eval.datasets.primock57 import PriMock57Dataset
    ds = PriMock57Dataset("/nonexistent/path/primock57")
    assert ds.items() == []
    assert ds.name == "primock57"


def test_acibench_returns_empty_for_missing_dir():
    from eval.datasets.acibench import ACIBenchDataset
    ds = ACIBenchDataset("/nonexistent/path/acibench")
    assert ds.items() == []
    assert ds.name == "acibench"


def test_dataset_adapters_are_real_seam():
    from eval.datasets.primock57 import PriMock57Dataset
    from eval.datasets.acibench import ACIBenchDataset
    assert issubclass(PriMock57Dataset, Dataset)
    assert issubclass(ACIBenchDataset, Dataset)


# ── Harness (fakes — no model loaded) ─────────────────────────────────────────

class _StaticDataset(Dataset):
    """In-memory dataset for harness tests."""

    def __init__(self, _items: list[DatasetItem]) -> None:
        self._items = _items

    @property
    def name(self) -> str:
        return "static"

    def items(self) -> list[DatasetItem]:
        return self._items


def _fake_audio() -> Audio:
    return Audio(source="fake", path=None)


def test_harness_empty_dataset_returns_empty_report():
    from tests.conftest import build_fake_scribe
    scribe, _, _ = build_fake_scribe()
    ctx = PatientContext(patient_ref="p", encounter_ref="e")
    report = EvalHarness(scribe, ctx).run(_StaticDataset([]))
    assert isinstance(report, EvalReport)
    assert report.metrics == {}


def test_harness_wer_perfect_when_reference_matches_fake_dialogue():
    from tests.conftest import build_fake_scribe
    from tests.fakes.dialogue import _DEFAULT_DIALOGUE

    # Build hypothesis from the dialogue the fake returns.
    ref_text = " ".join(u.text for u in _DEFAULT_DIALOGUE.utterances)

    scribe, _, _ = build_fake_scribe()
    ctx = PatientContext(patient_ref="p", encounter_ref="e")
    item = DatasetItem(item_id="t01", audio=_fake_audio(), reference_transcript=ref_text)
    report = EvalHarness(scribe, ctx).run(_StaticDataset([item]))

    assert "asr" in report.metrics
    assert report.metrics["asr"]["wer"] == pytest.approx(0.0)


def test_harness_completeness_scores_present():
    from tests.conftest import build_fake_scribe
    scribe, _, _ = build_fake_scribe()
    ctx = PatientContext(patient_ref="p", encounter_ref="e")
    item = DatasetItem(
        item_id="t02",
        audio=_fake_audio(),
        reference_note="patient reports sore throat for three days",
    )
    report = EvalHarness(scribe, ctx).run(_StaticDataset([item]))

    assert "completeness" in report.metrics
    assert "rouge1" in report.metrics["completeness"]
    assert "rougeL" in report.metrics["completeness"]


def test_harness_averages_multiple_items():
    from tests.conftest import build_fake_scribe
    scribe, _, _ = build_fake_scribe()
    ctx = PatientContext(patient_ref="p", encounter_ref="e")
    items = [
        DatasetItem(item_id=f"t{i:02d}", audio=_fake_audio(),
                    reference_note="patient reports sore throat")
        for i in range(3)
    ]
    report = EvalHarness(scribe, ctx).run(_StaticDataset(items))
    assert "completeness" in report.metrics


def test_harness_uses_only_public_scribe_seam():
    # Structural: EvalHarness only accepts a Scribe, not internals.
    import inspect
    sig = inspect.signature(EvalHarness.__init__)
    assert "scribe" in sig.parameters
    assert "ctx" in sig.parameters


# ── Report rendering ──────────────────────────────────────────────────────────

def test_render_report_empty():
    rendered = render_report(EvalReport(metrics={}))
    assert "No metrics" in rendered


def test_render_report_contains_component_and_metric():
    report = EvalReport(metrics={"asr": {"wer": 0.15}})
    rendered = render_report(report)
    assert "asr" in rendered
    assert "wer" in rendered
    assert "0.1500" in rendered


def test_render_report_multi_component():
    report = EvalReport(metrics={
        "asr": {"wer": 0.12},
        "completeness": {"rouge1": 0.72, "rougeL": 0.68},
    })
    rendered = render_report(report)
    assert "completeness" in rendered
    assert "rouge1" in rendered
    assert "0.7200" in rendered
