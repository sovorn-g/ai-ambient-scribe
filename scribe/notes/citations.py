"""CitationValidator — pure, deterministic, no model, no seam (design.md §3).

Turns a raw SOAPNote into a GroundedNote by validating and stripping citations.

Policy: invalid citations are stripped per-claim; a claim with zero remaining
valid citations is dropped entirely. This is the product's "never fabricates"
guarantee — enforced structurally, not by remembering to check a flag.

Returns GroundedNote if any claims survive; Violations if every claim was
dropped. NoteGenerator.generate consumes this and returns an empty GroundedNote
on Violations (drop-bad-claims policy, not re-ask).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scribe.domain.types import Claim, Dialogue, GroundedNote, SOAPNote, SpanRef, Utterance


@dataclass
class Violation:
    section: str
    claim_text: str
    reason: str


@dataclass
class Violations:
    items: list[Violation] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.items)


_SECTIONS = ("subjective", "objective", "assessment", "plan")


class CitationValidator:
    """Validate citations; produce a GroundedNote or Violations. Pure."""

    def validate(self, note: SOAPNote, dialogue: Dialogue) -> GroundedNote | Violations:
        index = {u.id: u for u in dialogue.utterances}
        violations: list[Violation] = []
        total_input = 0
        sections: dict[str, list[Claim]] = {}

        for section in _SECTIONS:
            raw_claims: list[Claim] = getattr(note, section)
            total_input += len(raw_claims)
            grounded: list[Claim] = []
            for claim in raw_claims:
                valid_refs = [ref for ref in claim.citations if _valid(ref, index)]
                if valid_refs:
                    grounded.append(Claim(text=claim.text, citations=valid_refs))
                else:
                    reason = "zero citations" if not claim.citations else "no valid citations"
                    violations.append(Violation(section=section, claim_text=claim.text, reason=reason))
            sections[section] = grounded

        surviving = sum(len(v) for v in sections.values())
        if total_input > 0 and surviving == 0:
            return Violations(items=violations)

        return GroundedNote(**sections)


def _valid(ref: SpanRef, index: dict[str, Utterance]) -> bool:
    utterance = index.get(ref.utterance_id)
    if utterance is None:
        return False
    if ref.char_span is not None:
        start, end = ref.char_span
        if start < 0 or end > len(utterance.text) or start > end:
            return False
    return True
