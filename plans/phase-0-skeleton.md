# Phase 0 — Walking Skeleton (freezes all seams)

> **Goal:** the thinnest end-to-end path that touches **every seam**, so integration risk dies on
> day one. Audio file → raw transcript → SOAP note → validated FHIR `DocumentReference` →
> human-gated write. Ugly on purpose.
>
> **Slice ref:** execute-plan-v2.md §4 "Slice 0"; design.md §7 row 0.
> **Depends on:** nothing (greenfield). · **Blocks:** *every other phase.*
> **Parallel-safe with:** nothing — this is **WAVE 0, run solo, merge to `main` before any fan-out.**

> ⚠️ **This phase is the contract for all concurrent work. Do NOT internally parallelize it.** The
> whole point is one coherent author getting the domain types and seam interfaces right. Everything
> downstream is "depth behind a frozen interface" — if these interfaces are wrong, parallel phases
> amplify the pain. Spend the rigor here.

## Context for a cold agent
Greenfield Python repo (only planning docs exist, no commits). Read `design.md` end-to-end first —
§1 (domain types), §2 (module map), §3 (deep modules), §4 (approval gate), §5 (seam inventory).
This phase **stands up every runtime seam with its thinnest adapter** and **writes the domain types
and fakes that all later phases code against.** Hardware target: Mac Mini M4, 16GB. Fully local,
zero cloud. Note generation runs through **Ollama** serving **Qwen2.5-7B-Instruct (q4)**.

## Files I OWN (create)
Lay down the full skeleton tree from design.md §2 (even where a slice later deepens it):

```
pyproject.toml                         # ALL deps for ALL phases, grouped/commented by phase (rule 3)
scribe/__init__.py
scribe/domain/types.py                 # §1 types — FROZEN after this phase
scribe/dialogue/__init__.py            # DialogueExtractor.extract(audio)->Dialogue
scribe/dialogue/transcriber/base.py    # Transcriber [seam] interface
scribe/dialogue/transcriber/mlx_whisper.py   # thin real adapter (large-v3-turbo)
scribe/dialogue/diarizer/base.py       # Diarizer [seam] interface + NullDiarizer (Slice 0 = none)
scribe/dialogue/aligner.py             # Aligner — pure; Slice-0 passthrough (no turns yet)
scribe/dialogue/roles.py               # RoleLabeller — pure; Slice-0 returns role=UNKNOWN
scribe/notes/__init__.py               # NoteGenerator.generate(dialogue)->SOAPNote (no grounding yet)
scribe/notes/prompt.py                 # plain SOAP prompt (pure)
scribe/notes/decode.py                 # parse model JSON -> SOAPNote (pure; lenient for now)
scribe/notes/llm/base.py               # LLMClient [SEAM] interface: complete(prompt, schema)->json
scribe/notes/llm/ollama.py             # real Ollama adapter (Qwen2.5-7B)
scribe/fhir/exporter.py                # FhirExporter.toDocumentReference(approved, ctx)->DocumentRef
scribe/runtime/model_host.py           # ModelHost — minimal single-model residency
scribe/runtime/audio.py                # AudioSource [SEAM] interface + FileAudioSource
scribe/app/scribe.py                   # Scribe facade — FROZEN public surface after this phase
scribe/app/drafts.py                   # DraftStore [seam] interface + InMemoryDraftStore
scribe/app/approval.py                 # approve(edited, approver)->ApprovedNote — the ONLY door (§4)
scribe/cli/main.py                     # Slice-0 CLI adapter (hardcoded wav, y/n gate)
scribe/composition.py                  # build_scribe(cfg) + per-seam factory STUBS (rule 2)
tests/fakes/__init__.py                # FROZEN shared fakes (rule 5)
tests/fakes/llm.py                     # FakeLLMClient(canned JSON)
tests/fakes/dialogue.py                # FakeDialogueExtractor(fixed Dialogue)
tests/fakes/audio.py                   # FakeAudioSource(fixed buffer)
tests/conftest.py                      # wiring helpers that build the graph from fakes
tests/test_skeleton_e2e.py            # end-to-end through fakes (no model loaded)
data/.gitignore                        # PriMock57/ACI-Bench live here, gitignored
README.md                              # 1-paragraph run instructions for the skeleton
```

## Frozen — do not touch (N/A — you create them)
You are the author of the frozen surfaces. Get them right:
- `scribe/domain/types.py` — every type in design.md §1.
- `scribe/app/scribe.py` — the two-method public surface.
- The factory-stub layout in `composition.py`.

## Interface contract (write these signatures EXACTLY — downstream phases depend on them)
From design.md §1 and §3. These are the load-bearing signatures:

```python
# scribe/domain/types.py  (use dataclasses or pydantic v2; encode the two invariants as types)
Audio, TranscriptSeg, SpeakerTurn, Utterance, Dialogue, SpanRef, Claim, SOAPNote
GroundedNote   # = SOAPNote where every Claim has >=1 valid SpanRef (invariant by construction)
PatientContext, Draft, EditedDraft, ApprovedNote, DocumentRef, EvalReport
Role = Enum(CLINICIAN, PATIENT, UNKNOWN)

# scribe/app/scribe.py  — FROZEN
class Scribe:
    def generateDraft(self, audio: Audio, ctx: PatientContext) -> Draft: ...
    def approveAndExport(self, edited: EditedDraft, approver: Approver) -> DocumentRef: ...

# scribe/app/approval.py  — the ONLY constructor of ApprovedNote (§4)
def approve(edited: EditedDraft, approver: Approver) -> ApprovedNote: ...

# seams
class Transcriber:   def transcribe(self, audio: Audio) -> list[TranscriptSeg]: ...
class Diarizer:      def diarize(self, audio: Audio) -> list[SpeakerTurn]: ...   # NullDiarizer -> []
class LLMClient:     def complete(self, prompt: str, schema: dict) -> dict: ...
class AudioSource:   def load(self) -> Audio: ...
class DraftStore:    def save(self, d: Draft) -> str; def get(self, id) -> Draft: ...
class DialogueExtractor: def extract(self, audio: Audio) -> Dialogue: ...
class NoteGenerator:     def generate(self, dialogue: Dialogue) -> SOAPNote: ...   # GroundedNote @ Phase 2
class FhirExporter:      def toDocumentReference(self, approved: ApprovedNote, ctx: PatientContext) -> DocumentRef: ...
```

In Slice 0: `NullDiarizer` returns `[]`; `Aligner`+`RoleLabeller` produce one `Dialogue` of
`UNKNOWN`-role utterances straight from the transcript; `NoteGenerator` does a plain prompt with no
citations (returns a `SOAPNote`, not yet `GroundedNote`). `Scribe.generateDraft` returns a `Draft`
(status=DRAFT) and **writes nothing** — the only writer is `approveAndExport`, behind `approve`.

## composition.py — the merge-safe layout (rule 2, critical)
```python
def _build_transcriber(cfg):   return MlxWhisperTranscriber(cfg)
def _build_diarizer(cfg):      return NullDiarizer()         # Phase 1 fills body
def _build_note_generator(cfg):return NoteGenerator(_build_llm(cfg))  # Phase 2 deepens
def _build_llm(cfg):           return OllamaLLMClient(cfg)   # Phase 4 may add model param
def _build_audio_source(cfg):  return FileAudioSource(cfg.audio_path)  # Phase 5 fills mic/stream
def _build_draft_store(cfg):   return InMemoryDraftStore()   # Phase 5 fills sqlite
def _build_model_host(cfg):    return ModelHost(cfg)         # Phase 4 deepens (multi-model)
def build_scribe(cfg) -> Scribe:   # call sequence FROZEN
    ...
```

## Tasks (TDD where a seam exists)
1. `domain/types.py` — encode §1; make `GroundedNote`/`ApprovedNote` unconstructable by invariant.
2. Write `tests/fakes/*` + `tests/test_skeleton_e2e.py` **first** (red): assert
   `generateDraft → approve → approveAndExport` produces a valid `DocumentRef` using **fakes only**.
3. Implement `Scribe`, `approve`, `DialogueExtractor`(passthrough), `NoteGenerator`(plain),
   `FhirExporter`(minimal R5), `InMemoryDraftStore`, `FileAudioSource` until e2e is green.
4. Real-path script: `MlxWhisperTranscriber` + `OllamaLLMClient` wired via `build_scribe`; the CLI
   plays a hardcoded PriMock57 `.wav` → note → `y/n` gate → writes FHIR JSON to disk.
5. `pyproject.toml`: declare **all** deps for **all** phases now (rule 3) — e.g. `mlx-whisper`,
   `sherpa-onnx`, `ollama`, `fhir.resources`, `pydantic`, `fastapi`, `jiwer`, `pyannote.metrics`,
   `scispacy`/`medspacy`, `pytest`. Group with `# phase N` comments.

## Tests
- `tests/test_skeleton_e2e.py` — full path through fakes, no model loaded, deterministic.
- Smoke: `python -m scribe.cli.main` on one hardcoded `.wav` (manual; needs Ollama + mlx-whisper).

## Acceptance (execute-plan-v2.md §4)
- [ ] One script runs **audio → note → validated FHIR → human-gated write**, end to end.
- [ ] `approve()` is the only path from `Draft` to `DocumentRef` (§4 — verify no bypass exists).
- [ ] e2e test green with fakes only (no Ollama/mlx needed in CI).
- [ ] Every seam interface + every domain type from design.md §1–§3 exists and is importable.

## Merge checklist
- [ ] `composition.py` has the per-seam factory stubs exactly as above (unblocks parallel phases).
- [ ] `pyproject.toml` lists all-phase deps (so no later phase edits it).
- [ ] `tests/fakes/` complete and documented as **frozen**.
- [ ] Tag/note the merge commit `phase-0-skeleton` — Wave 1 branches from here.
