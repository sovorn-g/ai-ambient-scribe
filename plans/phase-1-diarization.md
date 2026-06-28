# Phase 1 — Diarization

> **Goal:** speaker-labeled dialogue into the LLM. Fill `Diarizer` + `Aligner` + `RoleLabeller`
> **inside** `DialogueExtractor`. The `DialogueExtractor.extract(audio) -> Dialogue` interface does
> **not** change — only its internals deepen.
>
> **Slice ref:** execute-plan-v2.md §4 step 1; design.md §7 row 1. *Highest technical risk — gets
> the most time.*
> **Depends on:** Phase 0 (merged). · **Blocks:** nothing hard (Phase 5 shows speaker labels, but
> can use UNKNOWN until this lands). · **Parallel-safe with:** Phase 2, Phase 3, Phase 5
> (disjoint module trees: this is `dialogue/`, they are `notes/`, `eval/`, `web/`).

## Context for a cold agent
Read `design.md §3` ("DialogueExtractor") and `execute-plan-v2.md §4 step 1`. Diarization is
**sherpa-onnx** (provably offline, no HF token, Apache-2.0; pyannote 3.1 is an accuracy fallback,
download-once-then-offline). The caller wants **attributed dialogue** — ASR, diarization, alignment,
and role-labelling are *internal* to `DialogueExtractor`; nothing above it changes. Phase 0 left
`NullDiarizer` (returns `[]`) and a passthrough aligner producing `UNKNOWN`-role utterances; you
replace those internals.

## Files I OWN (create/edit)
```
scribe/dialogue/diarizer/sherpa_onnx.py     # new real Diarizer adapter
scribe/dialogue/aligner.py                  # deepen: align TranscriptSeg ↔ SpeakerTurn → utterances
scribe/dialogue/roles.py                    # deepen: heuristic CLINICIAN/PATIENT labelling
scribe/dialogue/__init__.py                 # wire real diarizer+aligner+roles in the extractor
scribe/composition.py :: _build_diarizer    # ONLY this factory body (rule 2)
tests/test_dialogue.py                      # new — your tests
data/.gitignore                             # add sherpa model path if needed (append only)
```

## Frozen — do not touch
- `scribe/domain/types.py`, `scribe/app/scribe.py`, `tests/fakes/**` (rules 4, 5).
- `scribe/composition.py` **except** the `_build_diarizer` body (rule 2).
- `scribe/notes/**`, `eval/**`, `web/**`, `scribe/api/**` (other phases' trees).

## Interface contract (consume; do not change)
- Input: `Audio`. Output: `Dialogue` = ordered `[Utterance]` where `Utterance =
  {id, role, text, timeSpan, speakerId}`. `Diarizer.diarize(audio) -> list[SpeakerTurn]`.
- `Aligner` and `RoleLabeller` are **pure functions** (design.md §5: NOT a seam) — test directly,
  no fakes needed.

## Tasks (TDD — these are pure, ideal for /tdd)
1. `Aligner`: given `[TranscriptSeg]` + `[SpeakerTurn]`, assign each transcript segment a `speakerId`
   by max temporal overlap → emit `[Utterance]`. Pure → red/green/refactor with hand-built fixtures.
2. `RoleLabeller`: map raw `speakerId`s → `CLINICIAN`/`PATIENT` via a documented heuristic
   (e.g. who speaks first / question-density). Pure → unit-test the heuristic directly.
3. `SherpaOnnxDiarizer`: wrap sherpa-onnx segmentation → `[SpeakerTurn]`. Behind the `Diarizer`
   seam; test the *adapter* shape with a tiny fixture, not model accuracy.
4. Wire all three into `DialogueExtractor`; fill `_build_diarizer`.
5. **Manual speaker-correction is the fallback** (a function to override a `speakerId`→role map);
   the *UI* for it is a Phase-5/stretch concern — expose the hook, don't build UI here.

## Tests
- `tests/test_dialogue.py`: aligner overlap cases (clean, overlapping, gap), role heuristic,
  diarizer adapter shape. Use real fixtures, not the model, in CI.

## Acceptance (execute-plan-v2.md §4 step 1)
- [x] Speaker-attributed `Dialogue` flows into the LLM (replaces UNKNOWN-only output).
- [ ] **≥80% of segments correctly attributed** on a sample PriMock57 consult (measure roughly here;
      Phase 3 computes formal DER). *Deferred: needs sherpa-onnx installed + a PriMock57 wav
      fetched into `data/`; CI covers the adapter shape + heuristic, not the accuracy number.*
- [x] Manual speaker-correction hook exists as the fallback (`apply_role_map` + `label_roles(role_map=...)`).
- [x] `DialogueExtractor.extract` signature unchanged; `tests/test_skeleton_e2e.py` still green.

## Merge checklist
- [x] Only `_build_diarizer` touched in `composition.py`.
- [x] No edits outside `scribe/dialogue/**` + `tests/test_dialogue.py` (+ the `_build_diarizer` body
      in `composition.py`, per rule 2).
- [x] Phase-0 e2e test still passes (interface stability proof).
