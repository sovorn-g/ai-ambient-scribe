"""Phase-2 tests — CitationValidator, grounded decode, and NoteGenerator.generate.

TDD tracer bullets, one behavior at a time.
"""

from __future__ import annotations

import pytest

from scribe.domain.types import (
    Claim,
    Dialogue,
    GroundedNote,
    Role,
    SOAPNote,
    SpanRef,
    TimeSpan,
    Utterance,
)
from scribe.notes.citations import CitationValidator, Violations


# ── helpers ──────────────────────────────────────────────────────────────────

def _dialogue(*utterances: tuple[str, str]) -> Dialogue:
    """Build a Dialogue from (id, text) pairs."""
    return Dialogue(
        utterances=[
            Utterance(
                id=uid,
                role=Role.UNKNOWN,
                text=text,
                time_span=TimeSpan(start=0.0, end=1.0),
                speaker_id="spk",
            )
            for uid, text in utterances
        ]
    )


def _soap(section: str, text: str, citations: list[SpanRef]) -> SOAPNote:
    """Build a SOAPNote with a single claim in the given section."""
    claim = Claim(text=text, citations=citations)
    return SOAPNote(**{section: [claim]})


# ── CitationValidator — behavior 1: valid citation passes ────────────────────

def test_valid_citation_produces_grounded_note():
    dialogue = _dialogue(("u0001", "My throat hurts."))
    note = _soap("subjective", "Patient reports sore throat.", [SpanRef(utterance_id="u0001")])

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, GroundedNote)
    assert len(result.subjective) == 1
    assert result.subjective[0].citations[0].utterance_id == "u0001"


# ── CitationValidator — behavior 2: fabricated utterance_id rejected ─────────

def test_fabricated_utterance_id_drops_claim():
    dialogue = _dialogue(("u0001", "Real utterance."))
    note = _soap("subjective", "A claim.", [SpanRef(utterance_id="FAKE-999")])

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, Violations)


def test_fabricated_utterance_id_mixed_with_valid_keeps_valid_citation():
    dialogue = _dialogue(("u0001", "Real utterance."))
    claim = Claim(
        text="Partially grounded.",
        citations=[
            SpanRef(utterance_id="FAKE-999"),
            SpanRef(utterance_id="u0001"),
        ],
    )
    note = SOAPNote(subjective=[claim])

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, GroundedNote)
    assert len(result.subjective[0].citations) == 1
    assert result.subjective[0].citations[0].utterance_id == "u0001"


# ── CitationValidator — behavior 3: out-of-range char_span ──────────────────

def test_out_of_range_char_span_strips_span_keeps_citation():
    """An out-of-bounds char_span strips the span but keeps the citation —
    the utterance_id is the grounding guarantee; char_span is UI sugar that
    LLMs cannot reliably produce (they emit global transcript offsets)."""
    dialogue = _dialogue(("u0001", "short"))  # len=5
    note = _soap(
        "subjective",
        "A claim.",
        [SpanRef(utterance_id="u0001", char_span=(0, 100))],  # 100 > 5
    )

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, GroundedNote)
    assert len(result.subjective) == 1
    assert result.subjective[0].citations[0].utterance_id == "u0001"
    assert result.subjective[0].citations[0].char_span is None


def test_valid_char_span_passes():
    dialogue = _dialogue(("u0001", "My throat hurts."))  # len=16
    note = _soap(
        "subjective",
        "Sore throat.",
        [SpanRef(utterance_id="u0001", char_span=(3, 9))],
    )

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, GroundedNote)


def test_negative_char_span_start_strips_span_keeps_citation():
    """A negative char_span start is invalid → strip the span, keep the citation."""
    dialogue = _dialogue(("u0001", "some text"))
    note = _soap(
        "subjective",
        "A claim.",
        [SpanRef(utterance_id="u0001", char_span=(-1, 4))],
    )

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, GroundedNote)
    assert result.subjective[0].citations[0].char_span is None


# ── CitationValidator — behavior 4: claim with zero citations ────────────────

def test_claim_with_zero_citations_is_dropped():
    dialogue = _dialogue(("u0001", "Real utterance."))
    note = SOAPNote(subjective=[Claim(text="No citations at all.", citations=[])])

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, Violations)


# ── CitationValidator — behavior 5: all-ungrounded → Violations ─────────────

def test_all_ungrounded_returns_violations():
    dialogue = _dialogue(("u0001", "Something said."))
    note = SOAPNote(
        subjective=[Claim(text="Made up.", citations=[SpanRef(utterance_id="ghost")])],
        objective=[Claim(text="Also made up.", citations=[SpanRef(utterance_id="ghost")])],
    )

    result = CitationValidator().validate(note, dialogue)

    assert isinstance(result, Violations)
    assert len(result.items) == 2


def test_empty_note_returns_empty_grounded_note():
    """An empty SOAPNote has no claims to violate — valid GroundedNote."""
    result = CitationValidator().validate(SOAPNote(), _dialogue())

    assert isinstance(result, GroundedNote)
    assert not result.all_claims()


# ── decode.py — behavior 6: citations parsed from model JSON ─────────────────

def test_decode_parses_citations():
    from scribe.notes.decode import parse_soap_note

    raw = {
        "subjective": [
            {
                "text": "Patient reports sore throat.",
                "citations": [{"utterance_id": "u0001"}],
            }
        ],
        "objective": [],
        "assessment": [],
        "plan": [],
    }
    note = parse_soap_note(raw)

    assert len(note.subjective[0].citations) == 1
    assert note.subjective[0].citations[0].utterance_id == "u0001"


def test_decode_parses_char_span():
    from scribe.notes.decode import parse_soap_note

    raw = {
        "subjective": [
            {
                "text": "Claim.",
                "citations": [{"utterance_id": "u0002", "char_span": [0, 5]}],
            }
        ],
        "objective": [],
        "assessment": [],
        "plan": [],
    }
    note = parse_soap_note(raw)

    assert note.subjective[0].citations[0].char_span == (0, 5)


def test_decode_tolerates_missing_citations_field():
    """Claims without a 'citations' key decode cleanly (backwards-compat)."""
    from scribe.notes.decode import parse_soap_note

    raw = {
        "subjective": [{"text": "No citations field."}],
        "objective": [],
        "assessment": [],
        "plan": [],
    }
    note = parse_soap_note(raw)

    assert note.subjective[0].text == "No citations field."
    assert note.subjective[0].citations == []


# ── NoteGenerator — behavior 7: grounded fake → GroundedNote with citations ──

def test_note_generator_returns_grounded_note_via_grounded_fake():
    from scribe.notes import NoteGenerator
    from tests.fakes.dialogue import _DEFAULT_DIALOGUE
    from tests.fakes.llm_grounded import FakeGroundedLLMClient

    generator = NoteGenerator(FakeGroundedLLMClient())
    result = generator.generate(_DEFAULT_DIALOGUE)

    assert isinstance(result, GroundedNote)
    assert result.all_claims()
    assert all(c.citations for c in result.all_claims())


# ── NoteGenerator — behavior 8: ungrounded fake → empty GroundedNote ─────────

def test_note_generator_drops_all_ungrounded_claims():
    """FakeLLMClient returns no citations → CitationValidator drops everything."""
    from scribe.notes import NoteGenerator
    from tests.fakes.dialogue import _DEFAULT_DIALOGUE
    from tests.fakes.llm import FakeLLMClient

    generator = NoteGenerator(FakeLLMClient())
    result = generator.generate(_DEFAULT_DIALOGUE)

    assert isinstance(result, GroundedNote)
    assert not result.all_claims()
