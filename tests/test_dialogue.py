"""Phase 1 — diarization tests.

Pure-logic units (Aligner, RoleLabeller) are tested directly with hand-built
fixtures. The SherpaOnnxDiarizer *adapter shape* is tested with a fake raw
segment list — no model loaded, no sherpa-onnx dep required in CI.

Acceptance covered:
  * Speaker-attributed Dialogue flows out of aligner + roles.
  * Manual speaker-correction hook exists as the fallback.
  * DialogueExtractor.extract signature unchanged (still calls align + label).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from scribe.domain.types import (
    Audio,
    Dialogue,
    Role,
    SpeakerTurn,
    TimeSpan,
    TranscriptSeg,
    Utterance,
)
from scribe.dialogue.aligner import align
from scribe.dialogue.diarizer.base import Diarizer, NullDiarizer
from scribe.dialogue.roles import apply_role_map, guess_role, label_roles


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _seg(text: str, start: float, end: float) -> TranscriptSeg:
    return TranscriptSeg(text=text, time_span=TimeSpan(start=start, end=end))


def _turn(speaker_id: str, start: float, end: float) -> SpeakerTurn:
    return SpeakerTurn(speaker_id=speaker_id, time_span=TimeSpan(start=start, end=end))


# ─────────────────────────────────────────────────────────────────────────────
# Aligner — max temporal overlap → speaker_id
# ─────────────────────────────────────────────────────────────────────────────
class TestAlignerOverlap:
    def test_clean_containment_picks_containing_turn(self):
        """Segment fully inside one turn → that turn's speaker."""
        segs = [_seg("hello", 1.0, 2.0)]
        turns = [
            _turn("spk:A", 0.0, 5.0),
            _turn("spk:B", 5.0, 10.0),
        ]
        d = align(segs, turns)
        assert d.utterances[0].speaker_id == "spk:A"

    def test_max_overlap_wins_when_turns_overlap_segment(self):
        """Two turns both overlap; the one with more overlap wins."""
        segs = [_seg("words", 4.0, 6.0)]  # 2s span
        turns = [
            _turn("spk:A", 0.0, 5.0),  # 1s overlap (4→5)
            _turn("spk:B", 5.0, 10.0),  # 1s overlap (5→6) — tie
        ]
        # Tie: first-max wins (stable). Assert it's one of the two deterministically.
        d = align(segs, turns)
        assert d.utterances[0].speaker_id in {"spk:A", "spk:B"}
        # Make the tie explicit: spk:B overlaps more.
        segs = [_seg("words", 4.5, 6.5)]  # 2s span
        turns = [
            _turn("spk:A", 0.0, 5.0),  # 0.5s overlap
            _turn("spk:B", 5.0, 10.0),  # 1.5s overlap
        ]
        d = align(segs, turns)
        assert d.utterances[0].speaker_id == "spk:B"

    def test_segment_in_gap_gets_unknown_speaker(self):
        """Segment falls between turns → speaker_id='spk:unknown'."""
        segs = [_seg("orphan", 12.0, 13.0)]
        turns = [
            _turn("spk:A", 0.0, 5.0),
            _turn("spk:B", 5.0, 10.0),
        ]
        d = align(segs, turns)
        assert d.utterances[0].speaker_id == "spk:unknown"
        assert d.utterances[0].role == Role.UNKNOWN

    def test_empty_text_segments_dropped_even_with_turns(self):
        """Slice-0 dropped empties in the no-turn branch; Phase 1 keeps that
        behaviour consistent in the turn-aware branch too."""
        segs = [
            _seg("keep", 0.0, 1.0),
            _seg("", 1.0, 2.0),  # dropped
            _seg("also keep", 2.0, 3.0),
        ]
        turns = [_turn("spk:A", 0.0, 10.0)]
        d = align(segs, turns)
        assert [u.text for u in d.utterances] == ["keep", "also keep"]
        assert all(u.speaker_id == "spk:A" for u in d.utterances)

    def test_no_turns_falls_back_to_unknown(self):
        """NullDiarizer path still works — every utterance UNKNOWN, spk:unknown."""
        segs = [_seg("a", 0.0, 1.0), _seg("b", 1.0, 2.0)]
        d = align(segs, turns=[])
        assert [u.text for u in d.utterances] == ["a", "b"]
        assert all(u.role == Role.UNKNOWN for u in d.utterances)
        assert all(u.speaker_id == "spk:unknown" for u in d.utterances)

    def test_utterance_ids_stable_and_zero_padded(self):
        segs = [_seg(f"t{i}", float(i), float(i + 1)) for i in range(3)]
        d = align(segs, turns=[_turn("spk:A", 0.0, 5.0)])
        assert [u.id for u in d.utterances] == ["u0000", "u0001", "u0002"]

    def test_utterance_time_span_matches_segment(self):
        segs = [_seg("x", 2.5, 4.5)]
        turns = [_turn("spk:A", 0.0, 10.0)]
        d = align(segs, turns)
        assert d.utterances[0].time_span.start == 2.5
        assert d.utterances[0].time_span.end == 4.5

    def test_empty_input_yields_empty_dialogue(self):
        d = align([], turns=[_turn("spk:A", 0.0, 1.0)])
        assert d.utterances == []


# ─────────────────────────────────────────────────────────────────────────────
# RoleLabeller — first-speaker heuristic + question-density tiebreaker
# ─────────────────────────────────────────────────────────────────────────────
class TestRoleLabellerHeuristic:
    def test_first_speaker_becomes_clinician(self):
        """In a typical consult the clinician speaks first (greeting/question)."""
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="Hello, what brings you in?",
                      time_span=TimeSpan(start=0, end=2), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="My throat hurts.",
                      time_span=TimeSpan(start=2, end=4), speaker_id="spk:B"),
        ])
        labelled = label_roles(d)
        assert labelled.utterances[0].role == Role.CLINICIAN
        assert labelled.utterances[1].role == Role.PATIENT

    def test_second_speaker_becomes_patient(self):
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="Hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="Hello",
                      time_span=TimeSpan(start=1, end=2), speaker_id="spk:B"),
        ])
        labelled = label_roles(d)
        roles_by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert roles_by_speaker == {"spk:A": Role.CLINICIAN, "spk:B": Role.PATIENT}

    def test_third_speaker_stays_unknown(self):
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="hello",
                      time_span=TimeSpan(start=1, end=2), speaker_id="spk:B"),
            Utterance(id="u0002", role=Role.UNKNOWN, text="hi",
                      time_span=TimeSpan(start=2, end=3), speaker_id="spk:C"),
        ])
        labelled = label_roles(d)
        by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert by_speaker == {"spk:A": Role.CLINICIAN, "spk:B": Role.PATIENT, "spk:C": Role.UNKNOWN}

    def test_question_density_breaks_tie_when_first_speaker_ambiguous(self):
        """If two speakers first appear at the same timestamp, first-appearance
        order is ambiguous (it's just utterance-list order). Fall back to
        question-density: the speaker who asks more questions is the clinician.

        Here spk:B is listed first (so naive first-appearance would label
        spk:B=CLINICIAN) but asks no questions; spk:A asks two. The tiebreak
        must flip the assignment so spk=A=CLINICIAN."""
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="It hurts when I swallow.",
                      time_span=TimeSpan(start=0, end=2), speaker_id="spk:B"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="What's the pain like? Where?",
                      time_span=TimeSpan(start=0, end=2), speaker_id="spk:A"),
        ])
        labelled = label_roles(d)
        by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert by_speaker["spk:A"] == Role.CLINICIAN
        assert by_speaker["spk:B"] == Role.PATIENT

    def test_empty_dialogue_returns_empty(self):
        labelled = label_roles(Dialogue(utterances=[]))
        assert labelled.utterances == []

    def test_single_speaker_becomes_clinician(self):
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="Hello?",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:only"),
        ])
        labelled = label_roles(d)
        assert labelled.utterances[0].role == Role.CLINICIAN

    def test_unknown_speaker_id_stays_unknown(self):
        """Segments that fell in a gap (spk:unknown) must not be mislabelled."""
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="orphan",
                      time_span=TimeSpan(start=10, end=11), speaker_id="spk:unknown"),
        ])
        labelled = label_roles(d)
        by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert by_speaker["spk:A"] == Role.CLINICIAN
        assert by_speaker["spk:unknown"] == Role.UNKNOWN


class TestRoleLabellerManualOverride:
    """Manual speaker-correction — the fallback when the heuristic is wrong."""

    def test_role_map_overrides_heuristic(self):
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="hello",
                      time_span=TimeSpan(start=1, end=2), speaker_id="spk:B"),
        ])
        # Heuristic would say A=CLINICIAN, B=PATIENT; clinician corrects:
        labelled = label_roles(d, role_map={"spk:A": Role.PATIENT, "spk:B": Role.CLINICIAN})
        by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert by_speaker == {"spk:A": Role.PATIENT, "spk:B": Role.CLINICIAN}

    def test_partial_role_map_overrides_only_listed_speakers(self):
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.UNKNOWN, text="hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.UNKNOWN, text="hello",
                      time_span=TimeSpan(start=1, end=2), speaker_id="spk:B"),
        ])
        labelled = label_roles(d, role_map={"spk:A": Role.PATIENT})
        by_speaker = {u.speaker_id: u.role for u in labelled.utterances}
        assert by_speaker["spk:A"] == Role.PATIENT  # overridden
        assert by_speaker["spk:B"] == Role.PATIENT  # heuristic still applied for un-mapped

    def test_apply_role_map_is_a_standalone_hook(self):
        """The correction hook must be callable without re-running the heuristic
        — Phase 5 UI calls this when the clinician fixes a speaker label."""
        d = Dialogue(utterances=[
            Utterance(id="u0000", role=Role.CLINICIAN, text="hi",
                      time_span=TimeSpan(start=0, end=1), speaker_id="spk:A"),
            Utterance(id="u0001", role=Role.PATIENT, text="hello",
                      time_span=TimeSpan(start=1, end=2), speaker_id="spk:B"),
        ])
        fixed = apply_role_map(d, {"spk:A": Role.PATIENT, "spk:B": Role.CLINICIAN})
        by_speaker = {u.speaker_id: u.role for u in fixed.utterances}
        assert by_speaker == {"spk:A": Role.PATIENT, "spk:B": Role.CLINICIAN}

    def test_guess_role_with_map_uses_map(self):
        assert guess_role("spk:X", role_map={"spk:X": Role.PATIENT}) == Role.PATIENT


# ─────────────────────────────────────────────────────────────────────────────
# SherpaOnnxDiarizer — adapter *shape* (no model loaded)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _FakeRawSegment:
    """Mimics sherpa_onnx.OfflineSpeakerDiarizationSegment shape."""
    start: float
    end: float
    speaker: int


class TestSherpaOnnxDiarizerShape:
    def test_module_imports_without_sherpa_onnx_installed(self):
        """Deferred import: the module must import even if sherpa-onnx isn't
        installed (CI doesn't pay for the optional dep)."""
        from scribe.dialogue.diarizer import sherpa_onnx as mod

        assert hasattr(mod, "SherpaOnnxDiarizer")

    def test_is_a_diarizer(self):
        from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer

        assert issubclass(SherpaOnnxDiarizer, Diarizer)

    def test_identifier_reports_model_and_clustering(self):
        from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer

        dz = SherpaOnnxDiarizer(model_path="some.tar.gz", num_threads=1, threshold=0.5)
        ident = dz.identifier
        assert "sherpa-onnx" in ident
        assert "some.tar.gz" in ident  # model provenance

    def test_segments_to_turns_is_pure_and_testable(self):
        """The raw-segment → SpeakerTurn mapping is a pure function the adapter
        delegates to. Tested directly with a fake raw segment list — no model."""
        from scribe.dialogue.diarizer.sherpa_onnx import segments_to_turns

        raw = [
            _FakeRawSegment(start=0.0, end=2.0, speaker=0),
            _FakeRawSegment(start=2.0, end=4.0, speaker=1),
            _FakeRawSegment(start=4.0, end=6.0, speaker=0),
        ]
        turns = segments_to_turns(raw)
        assert len(turns) == 3
        assert all(isinstance(t, SpeakerTurn) for t in turns)
        assert [t.speaker_id for t in turns] == ["spk:0", "spk:1", "spk:0"]
        assert turns[0].time_span.start == 0.0
        assert turns[0].time_span.end == 2.0

    def test_diarize_raises_runtime_error_when_sherpa_onnx_missing(self, monkeypatch):
        """If sherpa-onnx isn't installed, the adapter must raise a helpful
        RuntimeError pointing at the install command — not an ImportError."""
        from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer

        dz = SherpaOnnxDiarizer(model_path="some.tar.gz")
        audio = Audio(source="file", path="/dev/null")

        import builtins

        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name == "sherpa_onnx":
                raise ImportError("no sherpa_onnx")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)
        with pytest.raises(RuntimeError, match="sherpa-onnx"):
            dz.diarize(audio)

    def test_diarize_raises_when_audio_has_no_path_and_no_samples(self):
        """Adapter requires either a path to load or in-memory samples; without
        either, it raises ValueError before trying to import sherpa-onnx."""
        from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer

        dz = SherpaOnnxDiarizer(model_path="some.tar.gz")
        audio = Audio(source="fake", path=None, samples=None)
        with pytest.raises(ValueError, match="path.*samples"):
            dz.diarize(audio)


# ─────────────────────────────────────────────────────────────────────────────
# DialogueExtractor — interface unchanged, internals now turn-aware.
# ─────────────────────────────────────────────────────────────────────────────
class TestDialogueExtractorWiring:
    """The extractor still calls align() then label_roles(); only the internals
    deepened. Verify with a tiny fake transcriber + fake diarizer."""

    def test_extract_calls_align_then_label_roles(self):
        from scribe.dialogue import DialogueExtractor

        class _FakeTranscriber:
            def transcribe(self, audio):
                return [_seg("Hello, what brings you in?", 0.0, 2.0),
                        _seg("My throat hurts.", 2.0, 4.0)]

            @property
            def identifier(self):
                return "fake:transcriber"

        class _FakeDiarizer(Diarizer):
            def diarize(self, audio):
                return [_turn("spk:A", 0.0, 2.0), _turn("spk:B", 2.0, 4.0)]

            @property
            def identifier(self):
                return "fake:diarizer"

        extractor = DialogueExtractor(_FakeTranscriber(), _FakeDiarizer())
        d = extractor.extract(Audio(source="fake"))
        # Aligner assigned speaker ids from turns; labeller applied heuristic.
        assert [u.speaker_id for u in d.utterances] == ["spk:A", "spk:B"]
        assert [u.role for u in d.utterances] == [Role.CLINICIAN, Role.PATIENT]

    def test_extract_with_null_diarizer_yields_unknown_roles(self):
        """Backward-compat: NullDiarizer still produces UNKNOWN utterances,
        so the phase-0 e2e path stays green."""
        from scribe.dialogue import DialogueExtractor

        class _FakeTranscriber:
            def transcribe(self, audio):
                return [_seg("hi", 0.0, 1.0)]

            @property
            def identifier(self):
                return "fake:transcriber"

        extractor = DialogueExtractor(_FakeTranscriber(), NullDiarizer())
        d = extractor.extract(Audio(source="fake"))
        assert d.utterances[0].role == Role.UNKNOWN
        assert d.utterances[0].speaker_id == "spk:unknown"
