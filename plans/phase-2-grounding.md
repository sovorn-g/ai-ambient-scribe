# Phase 2 — Span-grounding + constrained JSON

> **Goal:** every SOAP claim cites transcript line ranges. Deepen `NoteGenerator` with constrained
> decode + `CitationValidator`, making the `GroundedNote` invariant **real**. The single most
> impressive feature and the TGA-safe "never fabricates" story.
>
> **Slice ref:** execute-plan-v2.md §4 step 2; design.md §3 ("NoteGenerator", "CitationValidator"),
> §7 row 2.
> **Depends on:** Phase 0 (merged). · **Blocks:** Phase 3b (grounding metric reuses this),
> Phase 5b (UI highlight needs citations in payload). · **Parallel-safe with:** Phase 1, Phase 3
> (WER/DER/completeness part), Phase 5a (disjoint trees: this is `notes/`).

## Context for a cold agent
Read `design.md §3` ("NoteGenerator", "CitationValidator") and `execute-plan-v2.md §4 step 2`.
`NoteGenerator` hides prompt construction, constrained-JSON decode, and **span-citation extraction +
validation**, sitting on the **thin** `LLMClient.complete(prompt, schema) -> json`. **Keep grounding
deep and shared inside `NoteGenerator`** — do *not* push it into per-model adapters (bad locality;
it would duplicate across Qwen/MedGemma/Llama). `CitationValidator` is pure, deterministic, no model,
no seam — it's exactly what makes a weak 7B trustworthy and exactly what the Phase-3 grounding metric
scores.

## Files I OWN (create/edit)
```
scribe/notes/citations.py                   # new — CitationValidator (DEEP, pure)
scribe/notes/prompt.py                      # deepen — prompt instructs the model to cite SpanRefs
scribe/notes/decode.py                      # deepen — constrained JSON → SOAPNote with citations
scribe/notes/__init__.py                    # wire CitationValidator into NoteGenerator.generate
scribe/composition.py :: _build_note_generator   # ONLY this factory body (rule 2)
tests/test_notes.py                         # new — your tests
tests/fakes/llm_grounded.py                 # NEW fake variant returning citation JSON (don't edit frozen fake)
```

## Frozen — do not touch
- `scribe/domain/types.py` — `GroundedNote`/`Claim`/`SpanRef` already exist from Phase 0; you make
  the invariant *enforced*, you do not redefine the types (rule 4).
- `scribe/app/scribe.py`, `tests/fakes/llm.py` (frozen original), `tests/fakes/dialogue.py`.
- `scribe/composition.py` except `_build_note_generator` (rule 2).
- `scribe/dialogue/**`, `eval/**`, `web/**`, `scribe/api/**`.

## Interface contract (consume; do not change)
- `LLMClient.complete(prompt, schema) -> dict` (thin — model swap is Phase 4's, not yours).
- `NoteGenerator.generate(dialogue: Dialogue) -> GroundedNote` — the return type *tightens* from
  `SOAPNote` to `GroundedNote`; the method name/arity is unchanged.
- `CitationValidator.validate(note: SOAPNote, dialogue: Dialogue) -> GroundedNote | Violations`
  (design.md §3) — pure.

## Tasks (TDD — CitationValidator is pure, ideal for /tdd)
1. `prompt.py`: instruct the model to emit, per claim, the supporting `utteranceId`(+`charSpan`).
2. `decode.py`: parse model JSON into `[Claim]` with `[SpanRef]`; constrained/lenient-repair as
   needed (pure).
3. `citations.py` `CitationValidator`: reject/strip any `Claim` whose `SpanRef` doesn't resolve to a
   real `Utterance` (and, where `charSpan` given, to real text) → returns a `GroundedNote` or
   `Violations`. **Pure → red/green/refactor first**, with fabricated-citation fixtures.
4. Wire into `NoteGenerator.generate`: model → decode → validate → `GroundedNote`. On violations,
   define the policy (drop ungrounded claims vs. re-ask) and document it.
5. Add `tests/fakes/llm_grounded.py` (canned JSON *with* citations) — exercise the full path with no
   model loaded.

## Tests
- `tests/test_notes.py`: valid citation passes; fabricated `utteranceId` rejected; out-of-range
  `charSpan` rejected; claim with zero citations cannot survive into a `GroundedNote`.

## Acceptance (execute-plan-v2.md §4 step 2 / §6)
- [ ] Every `Claim` in the output `GroundedNote` has ≥1 valid `SpanRef` (invariant enforced).
- [ ] No ungrounded content can reach a `Draft` (verify with a fabricating fake LLM → all dropped).
- [ ] `NoteGenerator.generate` returns a `GroundedNote`; e2e test still green.
- [ ] Grounding logic lives in `notes/`, **not** in any `LLMClient` adapter (locality check).

## Merge checklist
- [ ] Only `_build_note_generator` touched in `composition.py`.
- [ ] No domain-type edits (rule 4); new fake added (not frozen one mutated, rule 5).
- [ ] Phase-0 e2e test still passes.
