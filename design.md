# AI Ambient Scribe — Codebase Design

> Companion to [execute-plan-v2.md](execute-plan-v2.md). The plan says *what* and *in what order*;
> this says *how the code is shaped*. Vocabulary follows the deep-module method: **module / interface /
> seam / adapter / depth / leverage / locality**. The aim — a lot of behaviour behind small interfaces,
> at clean seams, testable through those seams.

The plan describes a *pipeline* (ASR → diarization → note → FHIR → UI). A pipeline is a data-flow story,
not a design. Wire six stages together in the FastAPI layer and that layer becomes a **shallow
integrator** — complexity leaks to the caller. This document places the **deep modules** and the **seams**
so depth lives in the core and the edges stay thin.

---

## 1. Domain types — the vocabulary that crosses seams
These types *are* part of every interface. Get them right and the modules almost fall out.

```
Audio          = handle to PCM samples (from file, mic, or played-recording stream)
TranscriptSeg  = { text, timeSpan, wordTimings? }          # internal artifact
SpeakerTurn    = { speakerId, timeSpan }                   # internal artifact
Utterance      = { id, role: CLINICIAN|PATIENT|UNKNOWN, text, timeSpan, speakerId }
Dialogue       = ordered [Utterance]                       # DialogueExtractor output
SpanRef        = { utteranceId, charSpan? }                # points into the Dialogue
Claim          = { text, citations: [SpanRef] }
SOAPNote       = { subjective:[Claim], objective:[Claim], assessment:[Claim], plan:[Claim] }
GroundedNote   = SOAPNote  WHERE every Claim has ≥1 valid SpanRef   # invariant, not a comment
PatientContext = { patientRef, encounterRef }              # hardcoded Slice 0; Synthea later
Draft          = { id, dialogue: Dialogue, note: GroundedNote, status=DRAFT, provenance }
EditedDraft    = Draft after human edits (still DRAFT)
ApprovedNote   = { note: GroundedNote, approver, approvedAt }   # GATED — see §4
DocumentRef    = FHIR R5 DocumentReference
EvalReport     = metrics table (per component, per model)
```

Two invariants are encoded in *types*, not checks: `GroundedNote` (no ungrounded claim can exist) and
`ApprovedNote` (cannot be constructed without sign-off). Make illegal states unrepresentable.

---

## 2. Module map (depth labelled)

```
scribe/  (Python — deep core + thin edges)
  domain/            types from §1 .......................... (no logic)
  dialogue/          DialogueExtractor ....................... DEEP
    transcriber/       Transcriber  [seam] → mlx_whisper, fake
    diarizer/          Diarizer     [seam] → sherpa_onnx, fake
    aligner.py         Aligner ............................... deep, pure, no seam
    roles.py           RoleLabeller .......................... pure heuristic, no seam
  notes/             NoteGenerator ........................... DEEP
    prompt.py          prompt construction ................... pure
    decode.py          constrained-JSON decode .............. pure
    citations.py       CitationValidator ..................... DEEP, pure, no seam
    llm/               LLMClient    [SEAM] → ollama, fake  ← the one real model seam
  fhir/              FhirExporter ............................ deep-ish, pure
  runtime/
    model_host.py      ModelHost ............................. internal, hidden (16GB residency)
    audio.py           AudioSource  [SEAM] → file, mic/stream, fake
  app/
    scribe.py          Scribe (facade) ....................... DEEP — the public surface
    drafts.py          DraftStore   [seam] → sqlite/file, in-mem fake
  api/               FastAPI adapter ......................... THIN adapter
  cli/               Slice-0 CLI adapter ..................... THIN adapter
  composition.py     build_scribe(config) — wiring root

eval/  (second caller — not runtime)
  harness.py         EvalHarness
  datasets/          Dataset [SEAM] → primock57, acibench
  metrics/           wer / der / grounding / completeness .... pure scorers

web/   (Next.js — frontend adapter over api/)
data/  (PriMock57, ACI-Bench, Synthea — pointers, gitignored)
tests/ (cross every seam through fakes)
```

---

## 3. The deep modules (small interface, lots behind it)

### `Scribe` — the public surface (DEEP)
```
generateDraft(audio: Audio, ctx: PatientContext) -> Draft
approveAndExport(edited: EditedDraft, approver: Approver) -> DocumentRef
```
Behind two methods sits the entire product. CLI, Next.js, and (partly) the eval are its **adapters** —
two+ callers, so this seam is **real**. `generateDraft` composes `DialogueExtractor` + `NoteGenerator`
and hands the model-residency handoff to `ModelHost`. *Deletion test:* delete `Scribe` and the
orchestration + the approval invariant scatter into every caller.

### `DialogueExtractor.extract(audio) -> Dialogue` (DEEP)
The caller wants *attributed dialogue* — never a transcript without speakers. So ASR, diarization,
alignment, and role-labelling are **internal seams**, not top-level modules. `Transcriber` and `Diarizer`
are private to its implementation and to its own tests; `Aligner` and `RoleLabeller` are pure functions.
*Deletion test:* delete it and "align transcript to turns, then label roles" reappears in the API layer.

### `NoteGenerator.generate(dialogue) -> GroundedNote` (DEEP)
Hides prompt construction, constrained-JSON decode, and **span-citation extraction + validation**. Depends
on a **thin** `LLMClient.complete(prompt, schema) -> json` — *the model swap lives there, not here.* If
`NoteGenerator` were the N-adapter seam, grounding logic would duplicate across every model adapter (bad
**locality**). Keep grounding deep and shared; let only the raw completion vary.

### `CitationValidator.validate(note, dialogue) -> GroundedNote | Violations` (DEEP, pure)
Turns a raw `SOAPNote` into a `GroundedNote` or rejects it. The grounding *enforcement* — deterministic,
no model, no seam (nothing varies across it). This is what makes a weak 7B trustworthy; it's also exactly
what the grounding metric scores. Pure function → trivially testable.

### `FhirExporter.toDocumentReference(approved, ctx) -> DocumentRef` (deep-ish, pure)
Hides R5 resource construction + validation. Returns a resource, writes nothing — side-effect-free.

### `ModelHost` (internal, hidden)
Owns "ensure model X resident within 16GB, evict others." The sequential-load dance from plan §2 is
**localized here**; no caller ever sees `load()`/`unload()`. Exposing residency would be a leaky, shallow
interface. *Deletion test:* delete it and the juggling spreads into every model adapter.

---

## 4. The approval gate is a *type*, not a step
`approveAndExport` accepts only an `ApprovedNote`, and the sole constructor is:
```
approve(edited: EditedDraft, approver: Approver) -> ApprovedNote   # the only door
```
The human-in-the-loop guarantee is **structural**: there is no path from `Draft` to `DocumentRef` that
skips `approve`. The Slice-0 CLI `y/n` and the Slice-5 UI button are two adapters onto the same door.
Nothing exported without sign-off — enforced by the type system, not by remembering to check a flag.

---

## 5. Seam inventory (the real-vs-hypothetical discipline)
> *One adapter = hypothetical seam. Two = real.* Don't gold-plate hypothetical seams.

| Seam | Adapters / callers | Verdict | Why |
|---|---|---|---|
| `Scribe` (public) | CLI + Next.js (+ eval) | **REAL** | Two caller tiers cross it. |
| `LLMClient` | Qwen / MedGemma / Llama (param) + fake; **app + eval** drive it | **REAL** | The bake-off *and* the local-privacy story pivot here. |
| `AudioSource` | File (Slice 0/eval) + Mic/Stream (demo/UI) + fake | **REAL** | This *is* the plan's "input source ≠ processing mode." |
| `Dataset` (eval) | PriMock57 + ACI-Bench | **REAL** | Two datasets, different artifacts. |
| `DraftStore` | sqlite/file + in-memory fake | **REAL (via test)** | The fake is the second adapter. |
| `Transcriber` | mlx-whisper only | **HYPOTHETICAL** | Interface yes; no swappability theatre. |
| `Diarizer` | sherpa-onnx only | **HYPOTHETICAL** | Same. pyannote is a *maybe*, not a seam yet. |
| `FhirExporter` | R5 only | **HYPOTHETICAL** | Define the interface, one adapter. |
| `Aligner`, `RoleLabeller`, `CitationValidator`, metric scorers | — | **NOT A SEAM** | Pure deterministic logic; nothing varies. Test directly. |
| `api`, `cli` | — | **NOT A SEAM** | They *are* adapters at the `Scribe` seam; thin, no logic. |

---

## 6. Composition root + testability
`composition.py :: build_scribe(config) -> Scribe` is the *only* place real adapters are constructed and
injected. Everything else **accepts dependencies, doesn't create them** — so tests build the graph with
fakes:

- **Fake `LLMClient`** (canned JSON) → exercise all of `CitationValidator` / decode / prompt with **no
  model loaded** — fast, deterministic. (Large adapter, tiny implementation.)
- **Fake `DialogueExtractor`** (fixed `Dialogue`) → test note-gen + export in isolation.
- **In-memory `DraftStore`** → test `Scribe` end-to-end with no DB.
- **Fake `AudioSource`** → feed a fixed buffer; no mic, no file.

**The eval is the proof the seams are right-shaped.** WER/DER drive the *internal* `Transcriber`/`Diarizer`
seams; grounding drives `CitationValidator`; completeness drives `NoteGenerator` over a varied `LLMClient`
model. If the harness ever has to monkeypatch internals to get a number, **the seam is wrong** — fix the
shape, don't reach past it. Side-effect discipline keeps this clean: `generateDraft` returns a `Draft`
(no write); the only writer is export, behind the gate.

---

## 7. Slice → module mapping (seams frozen Slice 0, deepened after)
The walking skeleton's real job: **stand up every seam with its thinnest adapter.** Later slices deepen
*implementations behind fixed interfaces* — the public surface never moves.

| Slice | What it builds | Touches |
|---|---|---|
| **0 Skeleton** | every seam, thinnest adapter | `Transcriber`=mlx-whisper, `Diarizer`=**none** (raw transcript), `NoteGenerator`=plain prompt (no grounding), `LLMClient`=Ollama/Qwen, `FhirExporter`=minimal, `DraftStore`=in-mem, `AudioSource`=file, gate=CLI |
| **1 Diarization** | fill `Diarizer` + `Aligner` + `RoleLabeller` *inside* `DialogueExtractor` | interface unchanged |
| **2 Grounding** | deepen `NoteGenerator` with `CitationValidator` + constrained decode | `GroundedNote` invariant now real |
| **3 Eval** | `eval/` harness, `Dataset` adapters, metric scorers (2nd caller) | drives existing seams |
| **4 Bake-off** | vary `LLMClient` model param through the harness | no new seam |
| **5 UI** | Next.js + `api/` adapters; `AudioSource`=mic/stream; `DraftStore`=sqlite | onto fixed `Scribe` surface |
| **6 Demo/docs** | — | — |

The skeleton kills integration risk precisely because **it freezes the seams on day one**; every later
slice is depth added behind an interface that already has a caller and a test.
```
