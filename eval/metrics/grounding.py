"""Grounding scorers — citation coverage + entity grounding (Phase 3b).

Both scorers are pure functions.  Entity grounding accepts an injected ``nlp``
callable so it can be tested without a model and swapped in production.

Design note: citation coverage reuses ``CitationValidator`` — the validation
logic lives there (design.md §3); we don't re-implement it here.
"""
from __future__ import annotations

from typing import Callable

from scribe.domain.types import Dialogue, SOAPNote


def score_citation_coverage(note: SOAPNote, dialogue: Dialogue) -> float:
    """Fraction of input claims with ≥1 valid SpanRef pointing into the dialogue.

    Reuses ``CitationValidator`` — strips invalid refs, drops fully-ungrounded
    claims, then computes surviving / input.  Returns 1.0 when the note is
    empty (nothing to ground).
    """
    from scribe.notes.citations import CitationValidator, Violations

    all_input = note.all_claims()
    if not all_input:
        return 1.0

    result = CitationValidator().validate(note, dialogue)
    if isinstance(result, Violations):
        return 0.0
    return len(result.all_claims()) / len(all_input)


def score_entity_grounding(
    note_text: str,
    transcript_text: str,
    nlp: Callable[[str], list[str]],
) -> float:
    """Fraction of medical entities in the note that appear in the transcript.

    Args:
        note_text:       Flat note text (e.g. from ``note_to_text``).
        transcript_text: Full dialogue transcript (plain text).
        nlp:             Callable ``text → [entity_string, …]``.
                         In production: wrap scispaCy; in tests: use a mock.

    Returns 1.0 when no entities are detected (nothing to ground).
    """
    entities = nlp(note_text)
    if not entities:
        return 1.0
    lower_transcript = transcript_text.lower()
    grounded = sum(1 for ent in entities if ent.lower() in lower_transcript)
    return grounded / len(entities)


def load_scispacy_nlp() -> Callable[[str], list[str]] | None:
    """Return a scispaCy NER callable, or ``None`` if the model is unavailable.

    To install the model:
        pip install scispacy
        pip install https://s3-us-west-2.amazonaws.com/ai2-s3-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
    """
    try:
        import spacy
        nlp = spacy.load("en_core_sci_sm")
        return lambda text: [ent.text for ent in nlp(text).ents]
    except Exception:
        return None
