# Phase 3 — Eval harness (cheap, deterministic, local — NO LLM-judge)

> **Goal:** the receipt that proves the stack wasn't picked by vibes. A second caller (`eval/`) over
> the existing seams. WER + DER + grounding + completeness on PriMock57/ACI-Bench. **No LLM-judge**
> (weak + circular — execute-plan-v2.md §8).
>
> **Slice ref:** execute-plan-v2.md §4 step 3 / §5 / §8; design.md §6, §7 row 3.
> **Depends on:** Phase 0 (merged). The **grounding metric (3b)** additionally needs Phase 2 merged.
> **Blocks:** Phase 4 (bake-off runs through this harness). · **Parallel-safe with:** Phase 1,
> Phase 2, Phase 5 (new `eval/` tree, touches no `scribe/` source — only imports frozen interfaces).

> **Split for the wave plan:** **3a** (harness scaffold + `Dataset` adapters + WER/DER/completeness)
> can run in Wave 1 immediately. **3b** (grounding/entity-grounding metric) is a small follow-up in
> Wave 2 once Phase 2 has merged. Do 3a first; it unblocks Phase 4's structure.

## Context for a cold agent
Read `design.md §6` ("the eval is the proof the seams are right-shaped") and `execute-plan-v2.md
§4 step 3, §5, §8`. **`eval/` is a *second caller*, not runtime** — it drives the existing `Scribe`/
`Transcriber`/`Diarizer`/`LLMClient` seams through `composition.build_scribe`. **If you ever need to
monkeypatch `scribe/` internals to get a number, the seam is wrong — stop and report it** (do not
reach past the interface). Data: **PriMock57** (real mock-consult audio, license-clean) + **ACI-Bench**
(reference notes). No PHI ever.

## Files I OWN (create)
```
eval/__init__.py
eval/harness.py                 # EvalHarness — drives build_scribe over a Dataset, collects metrics
eval/datasets/base.py           # Dataset [SEAM] interface
eval/datasets/primock57.py      # audio + (where available) transcript refs
eval/datasets/acibench.py       # reference notes for completeness
eval/metrics/wer.py             # jiwer
eval/metrics/der.py             # pyannote.metrics
eval/metrics/completeness.py    # MEDCON / ROUGE vs ACI-Bench (label "completeness", NEVER faithfulness)
eval/metrics/grounding.py       # 3b — citation coverage + entity grounding (needs Phase 2)
eval/report.py                  # render EvalReport table (per component, per model)
tests/test_eval.py              # metric scorers are pure → unit-test directly
data/.gitignore                 # append dataset paths
```

## Frozen — do not touch
- All of `scribe/**` (you are a *caller*; import, don't edit). No `composition.py` edits.
- `scribe/domain/types.py` (use `EvalReport` as-is). Other phases' trees.

## Interface contract (consume; do not change)
- `build_scribe(cfg) -> Scribe`; `Scribe.generateDraft`. `Dataset.items() -> [(Audio, refs)]`.
- Metric scorers are **pure functions** (design.md §5: NOT a seam) — `score(pred, ref) -> float`.
- `LLMClient` is varied by **config/param** (Phase 4), not by editing adapters here.

## Tasks (TDD — scorers are pure, ideal for /tdd)
**3a (Wave 1):**
1. `Dataset` seam + `primock57`/`acibench` adapters (two adapters → real seam, design.md §5).
2. `wer.py` (jiwer), `der.py` (pyannote.metrics), `completeness.py` (MEDCON/ROUGE vs ACI-Bench) —
   pure scorers, unit-tested on tiny fixtures.
3. `harness.py`: run `build_scribe` over a `Dataset`, capture transcript/dialogue/note, score, emit
   `EvalReport`. `report.py`: render the table.
**3b (Wave 2, after Phase 2):**
4. `grounding.py`: **citation coverage** (% of claims with a valid span — reuse Phase 2's
   `CitationValidator` logic, don't re-implement) + **entity grounding** (every med/dose/condition in
   the note traces to the transcript, via scispaCy/medspaCy NER).
5. Add the **5-note human-eyeball** sanity checklist to `report.py` output.

## Tests
- `tests/test_eval.py`: WER on known pairs, DER on a toy RTTM, completeness on a fixture, grounding
  coverage on a `GroundedNote` with one fabricated claim (expect coverage < 1.0).

## Acceptance (execute-plan-v2.md §6 / §8)
- [ ] WER, DER, grounding (citation + entity), completeness (MEDCON) computed on the primary backend.
- [ ] **No LLM-judge anywhere.** Completeness is labelled *completeness*, never faithfulness.
- [ ] Harness uses only public seams (no internal monkeypatching).
- [ ] `EvalReport` renders a per-component / per-model table ready for Phase 4 to extend.

## Merge checklist
- [ ] Zero edits under `scribe/**`. New `eval/` tree only.
- [ ] 3a mergeable independently of Phase 2; 3b gated on Phase 2 merge.
- [ ] Metric scorers pure + unit-tested.
