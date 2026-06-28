# Phase 5 — Polished Next.js UI (the "polished product" hill)

> **Goal:** record/play → live-ish transcript → editable SOAP w/ speaker labels →
> **hover-a-claim-to-highlight-its-transcript-span** → approve → export, with a loud
> **"DRAFT — requires clinician approval"** state. *This is where the hill is won.* Biggest single
> time sink.
>
> **Slice ref:** execute-plan-v2.md §4 step 5 / §7 (demo); design.md §7 row 5, §4 (approval gate).
> **Depends on:** Phase 0 (merged) for the `Scribe` surface. **5b** (citation-highlight) needs
> Phase 2 merged. · **Blocks:** Phase 6 (demo). · **Parallel-safe with:** Phases 1–4 (new `web/` +
> `scribe/api/` tree; the only `scribe/` files it touches are *new* adapters at frozen seams).
> **Wave:** **5a** (shell + `api/` + record/play/edit/approve over UNKNOWN-or-real dialogue) in
> Wave 1; **5b** (hover-highlight wiring) in Wave 2 after Phase 2.

## Context for a cold agent
Read `design.md §3` ("Scribe"), `§4` (approval gate as a *type*), `execute-plan-v2.md §4 step 5,
§7`. The UI and the Phase-0 CLI are **two adapters onto the same `Scribe` door** — the
human-in-the-loop guarantee is structural: there is **no path from `Draft` to `DocumentRef` that
skips `approve`** (§4). Build `scribe/api/` (FastAPI) thinly over `Scribe`; the Next.js app talks to
it. New runtime adapters: `AudioSource`=mic/stream (this *is* the plan's "input source ≠ processing
mode" — the demo plays a recording *into the live pipeline*) and `DraftStore`=sqlite.

## Files I OWN (create/edit)
```
scribe/api/__init__.py
scribe/api/app.py                       # FastAPI adapter over Scribe.generateDraft / approveAndExport
scribe/api/schemas.py                   # request/response pydantic (NOT domain types — DTOs)
scribe/runtime/audio.py :: MicStreamAudioSource   # new adapter at the AudioSource seam
scribe/app/drafts.py :: SqliteDraftStore          # new adapter at the DraftStore seam
scribe/composition.py :: _build_audio_source, _build_draft_store   # ONLY these bodies (rule 2)
web/                                    # entire Next.js app (new tree)
tests/test_api.py                       # api adapter tests (through fakes)
```
> `runtime/audio.py` and `app/drafts.py` were created by Phase 0 with the file-/in-mem adapters and
> are not owned by any Wave-1 *other* phase, so adding a second adapter class is conflict-free.

## Frozen — do not touch
- `scribe/domain/types.py`, `scribe/app/scribe.py`, `scribe/app/approval.py` (§4 — the gate is the
  product's trust story; consume it, never bypass it). `tests/fakes/**`.
- `scribe/composition.py` except `_build_audio_source` / `_build_draft_store` (rule 2).
- `scribe/notes/**`, `scribe/dialogue/**`, `eval/**` (other phases). **5b** *reads* Phase 2's
  citation payload via the API — it does not edit `notes/`.

## Interface contract (consume; do not change)
- `Scribe.generateDraft(audio, ctx) -> Draft`; `Scribe.approveAndExport(edited, approver) ->
  DocumentRef`; `approve(edited, approver) -> ApprovedNote` is the **only** export door.
- `GroundedNote.Claim.citations: [SpanRef{utteranceId, charSpan}]` — the data the hover-highlight
  binds to (available once Phase 2 is merged; until then claims may be sparse/UNKNOWN).
- `AudioSource.load() -> Audio`, `DraftStore.save/get`.

## Tasks
**5a (Wave 1):**
1. `scribe/api/app.py`: thin FastAPI over `Scribe` (generate, fetch draft, edit, approve+export).
   Keep it an **adapter** — no orchestration logic (design.md §5: api is NOT a seam).
2. `MicStreamAudioSource` + `SqliteDraftStore`; fill the two factory bodies.
3. `web/`: record/play a consult, show transcript + editable SOAP with speaker labels, **loud DRAFT
   banner**, edit one field, Approve button → export. Fallback if time-short: a **thinner Next.js
   happy-path** (NOT a drop back to Streamlit — execute-plan-v2.md §4 step 5).
**5b (Wave 2, after Phase 2):**
4. Bind hover-on-a-claim → highlight its `SpanRef` range in the transcript pane (the signature
   feature). Render the citation provenance.

## Tests
- `tests/test_api.py`: generate→edit→approve→export happy path through **fakes** (no model);
  assert **no export endpoint can produce a `DocumentRef` without `approve`** (gate enforced).
- Frontend: minimal component/e2e for the approve flow + DRAFT state (per `web/` tooling).

## Acceptance (execute-plan-v2.md §6 / §7)
- [ ] Edit-and-approve UI; nothing saved without human sign-off; visible **DRAFT** state.
- [ ] Play a PriMock57 consult **into the live pipeline** → speaker-attributed grounded note appears.
- [ ] Hover a claim → its transcript span highlights (5b, once Phase 2 merged).
- [ ] Approve → FHIR `DocumentReference` exported. CLI and UI share the same `approve` door.

## Merge checklist
- [ ] Only `_build_audio_source` / `_build_draft_store` touched in `composition.py`.
- [ ] No edits to the `Scribe` facade or the approval gate (rule 4).
- [ ] 5a mergeable without Phase 2; 5b gated on Phase 2 merge.
