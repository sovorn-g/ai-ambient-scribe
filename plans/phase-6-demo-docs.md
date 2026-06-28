# Phase 6 — Demo video, README, architecture diagram, eval report

> **Goal:** package the finished product. The money shot: *"two people just talked and a trustworthy,
> traceable note fell out."*
>
> **Slice ref:** execute-plan-v2.md §4 step 6 / §7 (demo); design.md §7 row 6.
> **Depends on:** Phases 1–5 all merged + green. · **Blocks:** nothing (final). · **Parallel-safe
> with:** nothing meaningful — **Wave 3, run last, solo.** (Docs touch shared README/markdown; no
> point parallelizing.)

## Context for a cold agent
Read `execute-plan-v2.md §6` (success criteria), `§7` (the demo), `§5/§8` (benchmark framing), and
skim `design.md` for the architecture story. The product is the deliverable; the benchmark is the
*receipt*. Frame faithfulness honestly: the **grounding feature** (span citations) is the
product-level trust mechanism; reference metrics (ROUGE/MEDCON) are **completeness only, never
labelled faithfulness** (§8). No LLM-judge anywhere.

## Files I OWN (create/edit)
```
README.md                       # full project README (supersedes Phase-0 stub)
docs/architecture.md            # architecture diagram + seam/deep-module narrative (from design.md)
docs/eval-report.md             # the Phase-3/4 numbers, rendered + interpreted
docs/demo.md                    # link/script for the demo video
plans/                          # (optional) mark phases done
```

## Frozen — do not touch
- All source under `scribe/**`, `eval/**`, `web/**` — this phase is **docs + media only**. If a doc
  reveals a real bug, file it; don't fix code in the docs phase unless it's a one-line caption-level
  correction agreed with the orchestrator.

## Tasks
1. **Demo video:** play a PriMock57 consult into the live pipeline → speaker-attributed grounded
   SOAP appears → clinician edits one field → approves → FHIR exported. Capture the **hover-claim →
   highlight-span** moment and the **DRAFT** state explicitly.
2. **README:** what it is, the hard constraints (fully local, no PHI, scribe-not-device / TGA
   boundary), the locked stack with one-line reasons (execute-plan-v2.md §3), quickstart, the demo.
3. **Architecture diagram:** the deep modules + seams from design.md §2/§3 (Scribe facade,
   DialogueExtractor, NoteGenerator, CitationValidator, FhirExporter, ModelHost; the `LLMClient` /
   `AudioSource` / `Dataset` seams). Show "input source ≠ processing mode."
4. **Eval report:** render WER, DER, grounding (citation + entity), completeness (MEDCON) across the
   note-LLM bake-off (Qwen vs MedGemma ± Llama). Interpret the general-vs-medical result. Label
   completeness as completeness. Note the 5-note human-eyeball sanity check.

## Acceptance (execute-plan-v2.md §6 — final gate for the whole project)
- [ ] All §6 success criteria demonstrably met and shown in the demo.
- [ ] Eval report present with all four metric families; **no LLM-judge**; completeness not
      mislabelled as faithfulness.
- [ ] README + architecture diagram tell the "polished, trustworthy, fully-local scribe" story.
- [ ] Demo video captures the money shot (grounded note falls out of a natural conversation).

## Merge checklist
- [ ] Docs/media only; zero source edits.
- [ ] All earlier phases merged and the full test suite green before recording the final demo.
