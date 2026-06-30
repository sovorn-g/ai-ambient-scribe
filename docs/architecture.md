# Architecture

> Companion to [`design.md`](../design.md) (the deep-module vocabulary) and
> [`execute-plan-v2.md`](../execute-plan-v2.md) (the build order). This page is
> the *picture*: how the pieces connect, where the seams sit, and why depth lives
> where it does.

## The one-paragraph story

A natural doctor–patient conversation is captured as audio. The audio flows
through one deep module that turns it into **speaker-attributed dialogue**, then
another that turns the dialogue into a **grounded SOAP note** (every claim cites
a transcript span). A clinician edits and approves the note; the *only* path
from draft to FHIR runs through that approval, enforced by the type system. The
whole thing runs on a single Mac Mini M4, 16GB, with zero cloud calls.

```
                            ┌─────────────────────────────────────────────┐
                            │                  Scribe (facade)            │
                            │   generateDraft(audio, ctx) -> Draft        │
                            │   approveAndExport(edited, appr) -> DocRef  │
                            │                                             │
   Audio  ───────────────▶  │  DialogueExtractor        NoteGenerator      │
   (file / mic /            │   Transcriber  [seam]       prompt.py         │
    stream / fake)          │   Diarizer     [seam]       decode.py         │
                            │   Aligner      (pure)       CitationValidator │
                            │   RoleLabeller (pure)       LLMClient [seam]  │
                            │                                             │
                            │  ModelHost (hidden residency, 16GB)          │
                            └───────────────┬─────────────────────────────┘
                                            │ ApprovedNote  (the only door)
                                            ▼
                                  FhirExporter  ──▶  DocumentReference (R5)
```

The two callers over `Scribe` are the **CLI** and the **Next.js UI** (via the
thin FastAPI adapter in `scribe/api/`). A third caller, the **eval harness**,
drives the same `generateDraft` surface to score it. Two+ callers is what makes
the `Scribe` seam *real* (not hypothetical).

## Deep modules (small interface, lots behind it)

| Module | Interface | Why it's deep |
|---|---|---|
| **`Scribe`** | `generateDraft`, `approveAndExport` | The whole product behind two methods. Hides orchestration + the approval invariant. *Delete it and the gate scatters into every caller.* |
| **`DialogueExtractor`** | `extract(audio) -> Dialogue` | Hides ASR + diarization + alignment + role-labelling as **internal** seams. The caller wants *attributed dialogue*, never a bare transcript. |
| **`NoteGenerator`** | `generate(dialogue) -> GroundedNote` | Hides prompt construction, constrained-JSON decode, and span-citation extraction + validation. Grounding logic is shared; only the raw completion varies (at the `LLMClient` seam). |
| **`CitationValidator`** | `validate(note, dialogue) -> GroundedNote \| Violations` | Pure, deterministic, no model. Turns a `SOAPNote` into a `GroundedNote` or rejects it. This is what makes a weak 7B trustworthy — and exactly what the grounding metric scores. |
| **`FhirExporter`** | `toDocumentReference(approved, ctx) -> DocumentRef` | Hides R5 resource construction + validation. Side-effect-free: returns a resource, writes nothing. |
| **`ModelHost`** | `ensure_resident(tag)` | Internal. Owns "load model X within 16GB, evict others." The sequential-load dance is localized here; no caller ever sees `load()`/`unload()`. |

## Seams — the real-vs-hypothetical discipline

> *One adapter = a hypothetical seam. Two adapters = a real seam.* We don't
> gold-plate hypothetical seams.

| Seam | Adapters | Verdict |
|---|---|---|
| `Scribe` (public) | CLI + Next.js (+ eval) | **REAL** |
| `LLMClient` | Qwen / MedGemma / Llama (param) + fake; app + eval drive it | **REAL** — the bake-off *and* the privacy story pivot here |
| `AudioSource` | File (Slice 0/eval) + Mic/Stream (demo/UI) + fake | **REAL** — this *is* "input source ≠ processing mode" |
| `Dataset` (eval) | PriMock57 + ACI-Bench | **REAL** |
| `DraftStore` | sqlite + in-memory fake | **REAL (via test)** |
| `Transcriber` | mlx-whisper only | HYPOTHETICAL — interface yes, no swap theatre |
| `Diarizer` | sherpa-onnx only | HYPOTHETICAL |
| `FhirExporter` | R5 only | HYPOTHETICAL |
| `Aligner`, `RoleLabeller`, `CitationValidator`, metric scorers | — | NOT A SEAM — pure deterministic logic, tested directly |

## Input source ≠ processing mode

This is the load-bearing distinction that keeps the demo honest
(execute-plan-v2.md §1). The pipeline always processes a **live ambient audio
stream**; the demo *feeds a recording into that live pipeline*. The `AudioSource`
seam is where that's modelled:

```
   file ──┐
   mic ───┼──▶  AudioSource.load() -> Audio  ──▶  DialogueExtractor.extract  ──▶  ...
   fake ──┘            (the seam)                      (mode-agnostic core)
```

The core never knows whether the audio came from a saved wav, a live mic, or a
test fake. The demo points the same `AudioSource=file` adapter at a PriMock57
recording; production points `AudioSource=mic` at the room. Same pipeline.

### Phase 7 — ambient listening (live capture, final batch truth)

Phase 7 makes "ambient" literal without turning the product into a realtime
clinical-ops platform. A new app-layer service sits beside `Scribe`:

```
  browser getUserMedia ──PCM16──▶ WebSocket /ambient/ws
                                       │
                                       ▼
                          AmbientSessionService
                            │           │
            audio buffer ◀─┘           └──▶ on End consultation:
            (UI only shows                write full WAV → Scribe.generateDraft
             the round listening dial)    (existing batch pipeline)
```

Key invariants (plans/phase-7-ambient-listening.md):

- **Live listening is record → stop → batch pipeline.** Click record, capture
  the conversation, click stop. No provisional truth is shown — the UI is a
  round voice-reactive listening dial.
- **Finalization reuses `Scribe.generateDraft`** on the FULL captured audio, so
  the final note quality is the same batch pipeline we benchmarked. The LLM
  never sees partial audio.
- **No new core types or seams.** `AmbientSessionService` is an app-layer module
  (`scribe/app/ambient.py`) that *consumes* `Scribe`; it does not alter the
  `Scribe` facade or the approval gate.
- **Background chunk transcription is a future extension, not current
  behavior.** For long sessions it could transcribe windows in the background
  while the listening dial keeps running visually — but the final LLM feed
  would still wait for the complete recording. Not yet implemented.

`build_ambient_service(cfg, scribe)` in `composition.py` wires the service with
the existing `Scribe` (no separate preview transcriber — finalization uses the
same `Scribe.generateDraft` path as batch upload).

## The approval gate is a *type*, not a step

```
   Draft  ──edit──▶  EditedDraft  ──approve()──▶  ApprovedNote  ──export──▶  DocumentRef
                          (DRAFT)                    (GATED)                    (written)
```

`approveAndExport` accepts only an `EditedDraft` and routes through `approve()` —
the **sole constructor** of `ApprovedNote`. There is no path from `Draft` to
`DocumentRef` that skips `approve`. The Slice-0 CLI `y/n` and the Slice-5 UI
button are two adapters onto the *same* door. Nothing is exported without
sign-off — enforced by the type system, not by remembering to check a flag.

## Composition root + testability

`scribe/composition.py :: build_scribe(config) -> Scribe` is the *only* place
real adapters are constructed and injected. Everything else **accepts
dependencies; it doesn't create them** — so tests build the graph with fakes:

- **Fake `LLMClient`** (canned JSON) → exercise all of `CitationValidator` /
  decode / prompt with no model loaded.
- **Fake `DialogueExtractor`** (fixed `Dialogue`) → test note-gen + export in
  isolation.
- **In-memory `DraftStore`** → test `Scribe` end-to-end with no DB.
- **Fake `AudioSource`** → feed a fixed buffer; no mic, no file.

The eval harness is the proof the seams are right-shaped: it drives the *public*
`generateDraft` surface only. If a metric ever had to monkeypatch internals to
get a number, the seam is wrong — fix the shape, don't reach past it.

## Layout

```
scribe/  (Python — deep core + thin edges)
  domain/            types (no logic)
  dialogue/          DialogueExtractor (DEEP)
    transcriber/       Transcriber  [seam] → mlx_whisper, fake
    diarizer/          Diarizer     [seam] → sherpa_onnx, fake
    aligner.py         Aligner      (pure, no seam)
    roles.py           RoleLabeller (pure, no seam)
  notes/             NoteGenerator (DEEP)
    prompt.py          prompt construction (pure)
    decode.py          constrained-JSON decode (pure)
    citations.py       CitationValidator (DEEP, pure)
    llm/               LLMClient [SEAM] → ollama, fake  ← the one real model seam
  fhir/              FhirExporter (deep-ish, pure)
  runtime/
    model_host.py      ModelHost (internal, hidden — 16GB residency)
    audio.py           AudioSource [SEAM] → file, mic/stream, fake
                    live_audio.py        PCM16 buffer + WAV writer (Phase 7)
  app/
    scribe.py          Scribe (facade, DEEP — the public surface)
    drafts.py          DraftStore [seam] → sqlite, in-mem fake
    ambient.py         AmbientSessionService (Phase 7 live listening)
  api/               FastAPI adapter (THIN) + /ambient/ws WebSocket (Phase 7)
  cli/               Slice-0 CLI adapter (THIN)
  composition.py     build_scribe(config) — wiring root; build_ambient_service (Phase 7)

eval/  (second caller — not runtime)
  harness.py         EvalHarness (drives Scribe.generateDraft only)
  bakeoff.py         BakeoffReport container
  models.py          ModelRegistry (the 3 bake-off tags)
  datasets/          Dataset [SEAM] → primock57, acibench
  metrics/           wer / der / grounding / completeness (pure scorers)
  report.py          markdown renderer

web/   (Next.js — frontend adapter over api/)
data/  (PriMock57, ACI-Bench — pointers, gitignored)
tests/ (cross every seam through fakes)
```
