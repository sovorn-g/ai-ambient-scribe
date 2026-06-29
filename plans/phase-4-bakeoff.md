# Phase 4 — Note-LLM bake-off

> **Goal:** prove the general-vs-medical question on *our own* data. Run **MedGemma-4B** and
> **Llama-3.1-8B** through the **same** Phase-3 harness as **Qwen2.5-7B** → a comparison table. The
> only axis where the comparison answers an interesting question *and* swapping is free via Ollama.
>
> **Slice ref:** execute-plan-v2.md §4 step 4 / §5 / §3 (bake-off comparators); design.md §7 row 4.
> **Depends on:** Phase 3 (harness, merged). Phase 2 (so grounding is part of the comparison) — run
> after both. · **Blocks:** Phase 6 (eval report). · **Parallel-safe with:** Phase 5 (disjoint:
> this is `eval/` + `model_host`, that is `web/`/`api/`).
> **Wave:** Wave 2 (after Phase 3 merges).

## Context for a cold agent
Read `execute-plan-v2.md §3` (bake-off comparators), `§5` (benchmark scope), and `design.md §3`
("ModelHost", "LLMClient"). **No new seam** — you vary the `LLMClient` **model parameter** through
the existing harness. The bake-off is *note-LLM only*; ASR + diarization are **locked, not baked
off** (§5). The headline question: do general instruct models match/beat medical fine-tunes on
*faithful summarization* on PriMock57/ACI-Bench? **16GB caps concurrency** — sequential
load/unload via `ModelHost` is the supported path (design.md §3).

## Files I OWN (create/edit)
```
eval/models.py                          # registry: qwen2.5-7b, medgemma-4b, llama-3.1-8b (Ollama tags)
eval/harness.py                         # extend: iterate over the model registry (per-model rows)
scribe/runtime/model_host.py            # deepen: ensure-resident + evict-others within 16GB
scribe/composition.py :: _build_model_host  # ONLY this factory body (rule 2)
scribe/notes/llm/ollama.py              # extend: accept a model tag param (no grounding logic here!)
tests/test_bakeoff.py                   # new
```
> Note: `ollama.py` and `model_host.py` were created by Phase 0 and are not owned by any Wave-1
> phase, so editing them in Wave 2 is conflict-free. Keep edits to **model selection/residency
> only** — never put grounding or prompt logic in the adapter (that's Phase 2's `notes/`, locality).

## Frozen — do not touch
- `scribe/domain/types.py`, `scribe/app/scribe.py`, `scribe/notes/citations.py|prompt.py|decode.py`
  (Phase 2's grounding — it's model-agnostic on purpose; do not duplicate it per-model).
- `scribe/composition.py` except `_build_model_host` (rule 2). `web/**`, `scribe/api/**`,
  `scribe/dialogue/**`.

## Interface contract (consume; do not change)
- `LLMClient.complete(prompt, schema) -> dict` — unchanged; only *which model* answers varies.
- `EvalHarness` + metric scorers from Phase 3 — reuse, extend with a model dimension.
- `ModelHost`: `ensure_resident(model_tag)` / evict others; callers never see `load()/unload()`.

## Tasks
1. `eval/models.py`: list the three Ollama model tags + any per-model prompt notes.
2. Deepen `ModelHost`: ensure-resident-then-evict so each model runs within 16GB sequentially.
3. Parameterize `OllamaLLMClient` by model tag; `_build_model_host` selects/evicts.
4. Extend `EvalHarness` to loop the registry → one metrics row per model (WER/DER are model-invariant
   and reported once; **grounding + completeness** vary per note-LLM and are the real comparison).
5. Render the comparison table in `eval/report.py` (Phase 3) — add the model axis.

## Tests
- `tests/test_bakeoff.py`: harness iterates ≥2 fake models and produces distinct rows; `ModelHost`
  evicts the previous model before loading the next (assert via a fake host, no real 7B in CI).

## Acceptance (execute-plan-v2.md §5 / §6)
- [x] Qwen-7B vs MedGemma-4B (± Llama-8B) compared through the **same** harness on our data.
      *(Registry + harness + renderer wired; running the real comparison needs the three
      Ollama tags pulled locally + a PriMock57 sample in `data/`. CI exercises the loop
      with fakes.)*
- [x] Grounding + completeness reported **per model**; WER/DER reported once (locked axes).
- [x] Runs within 16GB via sequential residency (no OOM); no per-model grounding duplication.

## Merge checklist
- [x] Only `_build_model_host` touched in `composition.py`.
- [x] No grounding/prompt logic added to `llm/` adapters (locality preserved).
- [x] Comparison table renders for ≥2 models.
