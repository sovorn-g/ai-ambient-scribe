# Implementation Plan — AI Ambient Scribe

This directory breaks [execute-plan-v2.md](../execute-plan-v2.md) (the *what/when*) and
[design.md](../design.md) (the *how the code is shaped*) into **self-contained phase handoffs**.
Each `phase-N-*.md` is written so a *cold* coding agent — one that has read only that file, this
README, `design.md`, and `execute-plan-v2.md` — can execute it without talking to the others.

Phase ⇄ Slice mapping is 1:1 with `design.md §7`:

| Phase | Slice | Title | Touches (owned module tree) |
|---|---|---|---|
| [0](phase-0-skeleton.md) | 0 | Walking skeleton — **freezes all seams** | everything, thinnest adapter |
| [1](phase-1-diarization.md) | 1 | Diarization | `scribe/dialogue/` internals |
| [2](phase-2-grounding.md) | 2 | Span-grounding + constrained decode | `scribe/notes/` internals |
| [3](phase-3-eval-harness.md) | 3 | Eval harness (no LLM-judge) | new `eval/` tree |
| [4](phase-4-bakeoff.md) | 4 | Note-LLM bake-off | `eval/` extension + `model_host` |
| [5](phase-5-ui.md) | 5 | Polished Next.js UI | new `web/` + `scribe/api/` |
| [6](phase-6-demo-docs.md) | 6 | Demo video, README, diagram, eval report | docs only |

---

## How to run this: the wave plan (concurrent worktrees)

The phases form a DAG, not a line. Run them in **waves**; within a wave, phases touch
**disjoint module trees** and merge cleanly.

```
            ┌─────────────────────────── WAVE 0 (serial, blocking) ───────────────────────────┐
            │  Phase 0  Skeleton — one agent, merge to main, FREEZE seams + domain types       │
            └──────────────────────────────────────┬──────────────────────────────────────────┘
                                                    │ (branch all of WAVE 1 from main @ phase-0)
        ┌───────────────┬───────────────────────────┼───────────────────────────┬──────────────────┐
        ▼               ▼                            ▼                           ▼                  
   WAVE 1a          WAVE 1b                      WAVE 1c                     WAVE 1d
   Phase 1          Phase 2                      Phase 3 (harness+WER/DER     Phase 5a (UI shell +
   Diarization      Grounding                    /completeness only)         api/ adapter; no
   dialogue/        notes/                        eval/                       citation-highlight yet)
        │               │                            │                           │
        │               ├──────────────┐             │                           │
        │               ▼              ▼             ▼                           ▼
        │        WAVE 2: Phase 3b   WAVE 2: Phase 5b (citation-highlight wiring — needs Phase 2 merged)
        │        grounding metric   
        │        (needs Phase 2)    WAVE 2: Phase 4 Bake-off (needs Phase 3 merged) → model_host deepen
        └───────────────┴────────────────────┬───────────────────────────────────┘
                                              ▼
                            ┌──────────── WAVE 3 (serial) ────────────┐
                            │  Phase 6  Demo + docs (everything green) │
                            └──────────────────────────────────────────┘
```

**Dependency edges (why the waves):**
- Everything depends on **Phase 0** (it writes the domain types + every seam interface + the
  composition root + the test fakes). Nothing parallel can start until it merges.
- **Phase 4** needs **Phase 3**'s harness (it just varies the `LLMClient` model through it).
- **Phase 3's grounding metric** reuses **Phase 2**'s `CitationValidator` logic → split as 3b.
- **Phase 5's** signature feature (hover-claim → highlight transcript span) needs **Phase 2**'s
  citations in the `GroundedNote` payload → the UI *shell* (5a) parallelizes; the *highlight
  wiring* (5b) waits for Phase 2.

**Suggested branch names:** `phase-0-skeleton`, `phase-1-diarization`, `phase-2-grounding`,
`phase-3-eval-harness`, `phase-4-bakeoff`, `phase-5-ui`, `phase-6-demo-docs`. Branch each wave
from `main` *after* the previous wave merges.

### If you'd rather not parallelize
Run phases **0 → 1 → 2 → 3 → 4 → 5 → 6 in order, one agent at a time.** The phase docs are
identical; you just ignore the wave grouping. The DAG was designed so that the dependency order
*is* numeric order — sequential is always safe.

---

## The merge-without-conflict protocol (read before any parallel work)

Concurrent worktrees merge cleanly **only** because of these four rules. They are baked into every
phase doc; this is the canonical statement.

1. **Ownership is exclusive.** Each phase doc has a **`Files I OWN`** list and a **`Frozen — do
   not touch`** list. Two parallel phases never write the same file. If a phase discovers it *needs*
   to edit a frozen file, that is a **stop-and-coordinate event**, not a free edit (see rule 4).

2. **`composition.py` is the one legitimately-shared file — and it's pre-partitioned.** Phase 0
   creates it with one empty private factory **stub per seam**:
   ```python
   def _build_diarizer(cfg):        ...  # Phase 1 fills this body
   def _build_note_generator(cfg):  ...  # Phase 2 fills this body
   def _build_audio_source(cfg):    ...  # Phase 5 fills this body
   def _build_draft_store(cfg):     ...  # Phase 5 fills this body
   def _build_model_host(cfg):      ...  # Phase 4 fills this body
   ```
   Each phase edits **only its own factory body** → edits are line-disjoint → merges are trivial.
   No phase edits `build_scribe()`'s call sequence; it's frozen by Phase 0.

3. **`pyproject.toml` is never edited after Phase 0.** Phase 0 pre-declares **all** dependencies
   for every slice (grouped/commented by phase). Downstream phases only `import` — they never touch
   the dependency list, so it can't conflict. (If a truly-unforeseen dep is needed, that's a rule-4
   coordination event.)

4. **The domain types (`scribe/domain/`) and the public `Scribe` facade are FROZEN after Phase 0.**
   `design.md §6`: *"If the harness ever has to monkeypatch internals to get a number, the seam is
   wrong — fix the shape, don't reach past it."* The same applies to every parallel phase: if you
   need to change a domain type or the `Scribe` signature, **stop**, because a sibling phase is
   coding against it right now. Surface it to the orchestrator; fix the seam in a short serial
   patch that everyone rebases onto.

5. **Tests: one file per module, never shared.** Phase 0 creates `tests/fakes/` (the shared fakes)
   and freezes them. Each later phase adds **its own** `tests/test_<module>.py`. If a phase needs a
   richer fake (e.g. a fake `LLMClient` that returns citation JSON), it **adds a new fake variant**
   beside the Phase-0 fake — it does not mutate the frozen one.

### Conflict-surface summary (what to expect at merge time)
| File | Writers | Conflict risk | Mitigation |
|---|---|---|---|
| `scribe/composition.py` | 1,2,4,5 | low | per-seam factory stubs (rule 2) |
| `scribe/domain/**` | Phase 0 only | none if frozen | rule 4 |
| `scribe/app/scribe.py` | Phase 0 only | none if frozen | rule 4 |
| `pyproject.toml` | Phase 0 only | none | rule 3 |
| `tests/fakes/**` | Phase 0 only | none | rule 5 |
| everything else | exactly one phase | none | exclusive ownership (rule 1) |

---

## Definition of done (from execute-plan-v2.md §6)
- [ ] Audio → transcript → speaker-attributed dialogue → grounded SOAP note, fully local.
- [ ] Every SOAP claim traceable to a transcript span (no ungrounded content).
- [ ] Valid FHIR `DocumentReference` (R5), linked to Patient/Encounter.
- [ ] Edit-and-approve UI; nothing saved without human sign-off; visible "DRAFT" state.
- [ ] Eval report: WER, DER, grounding (citation + entity-grounding), completeness (MEDCON)
      across the note-LLM bake-off — **no LLM-judge**.

## Each phase doc's template
`Goal` · `Slice ref` · `Depends on / Blocks / Parallel-safe with` · `Context for a cold agent` ·
`Files I OWN` · `Frozen — do not touch` · `Interface contract` · `Tasks (TDD at seams)` ·
`Tests` · `Acceptance` · `Merge checklist`.
