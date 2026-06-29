# Demo

> **The money shot:** *two people just talked and a trustworthy, traceable note
> fell out.* Not raw speed — a short processing wait is normal and expected for
> ambient scribes. The point is the traceable, grounded note that appears from a
> natural conversation.

## Setup (one time)

```bash
# 1. Ollama daemon + the baseline note model (UI defaults to qwen2.5:7b)
brew services start ollama
ollama pull qwen2.5:7b-instruct-q4_K_M

# 2. Python adapters + scispaCy NER + sherpa diarization models + PriMock57
#    (full one-liners in README.md §Quickstart)

# 3. API (FastAPI :8000) + Web (Next.js :3000)
./dev.sh
```

Open http://localhost:3000. The masthead shows `Local · M4 · FHIR R5` and a live
API status dot.

## The script

This is the beat-by-beat script for the demo video. It plays a PriMock57
consultation **into the live pipeline** (input source = file; processing mode =
the same ambient-stream path production uses — see
[docs/architecture.md](architecture.md) §"Input source ≠ processing mode").

| # | Beat | What the viewer sees |
|---|---|---|
| 1 | **Context** | The dashboard hero: *"Fully local clinical AI — audio consultation to FHIR R5 note, with mandatory clinician sign-off before anything is saved."* Patient + Encounter refs are pre-filled. The **01 Upload → 02 Review → 03 Export** step bar is at step 01. |
| 2 | **Upload** | Drop a PriMock57 `.wav` (e.g. `data/primock57/day1_consultation01.wav`). The file uploads, the step bar advances and an elapsed timer starts ticking. A spinner card reads *"Running pipeline… Transcription → Speaker diarization → SOAP note generation."* |
| 3 | **The note falls out** | The spinner is replaced by a split view: left = **speaker-attributed transcript** (CLINICIAN / PATIENT turns with timestamps and coloured rails); right = **editable SOAP note** (S/O/A/P sections). Above both: a loud **DRAFT — requires clinician approval** banner. The meta row shows Patient · Encounter · Utterances. |
| 4 | **Show grounding (the trust moment)** | Each SOAP claim carries a `SpanRef` citation pointing at a transcript utterance — a small `N cites` badge sits beside each grounded claim. Hovering (or keyboard-focusing) a claim snaps the transcript pane to the cited utterance via `scrollIntoView`, tints it amber, drops a `cited` chip beside the speaker label, and wraps the exact evidence phrase in a `<mark>` when `char_span` is present. This is the signature feature — the on-screen proof that every claim traces to something actually said. |
| 5 | **Clinician edits one field** | Click into any claim text area and edit it (or `+ add entry` / `✕` remove). The note is clearly editable; the DRAFT banner stays until sign-off. |
| 6 | **Approve → export** | Enter approver name in the Approve section and click Approve. The view flips to a green *"Note approved & exported"* card: *"A FHIR R5 DocumentReference has been generated and signed off. Nothing left the draft state without your review."* |
| 7 | **The receipt** | The full FHIR R5 `DocumentReference` JSON is rendered below the success card. `← new consultation` resets. |

## Recording recipe

1. Run `./dev.sh` and confirm the API dot is green at http://localhost:3000.
2. Use a PriMock57 wav with a clear medication + condition in the dialogue so
   the grounding story is obvious (e.g. `day1_consultation01.wav`).
3. Screen-record (macOS `Cmd+Shift+5` → Record) at 1080p. Capture the whole
   browser viewport so the DRAFT banner and step bar stay in frame.
4. Narrate beats 1–7 above. For beat 4, **say aloud** what each claim cites
   (read the transcript line the claim came from) — this is the traceability
   story even when the on-screen hover highlight is not wired.
5. Trim the processing wait (beat 2's spinner) but **leave a beat of it** so the
   viewer sees the pipeline is real, not pre-baked.
6. Save as `docs/demo.mp4` (gitignored — too large for the repo; host
   separately and link from here).

## Citation highlighting — wired (Phase 5b)

The Phase-5 plan (`plans/phase-5-ui.md` §5b) scoped **hover-a-claim →
highlight-its-transcript-span** as the signature trust feature. It is now wired
end-to-end:

- `GroundedNote.Claim.citations` carries `SpanRef{utterance_id, char_span}`
  from the LLM through `CitationValidator` through the API
  (`web/lib/types.ts :: Claim.citations`) into the UI.
- `SOAPEditor` fires `onHoverCitations(claim.citations)` on row hover **or**
  keyboard focus (so the binding is accessible, not pointer-only) and clears on
  leave/blur. A provenance badge (`N cites`) sits beside each grounded claim —
  the affordance that says "this claim is traceable."
- `page.tsx` lifts a single `activeCitation: SpanRef | null` and passes the
  **first** citation of the hovered claim to `TranscriptPane` (multi-cite
  claims scroll to the first; the rest are tinted by id match).
- `TranscriptPane` per-row `useEffect` calls
  `scrollIntoView({ block: "center", behavior: "smooth" })` on the cited
  utterance — the *auto-scroll is the load-bearing part*: a long scrollable
  transcript would otherwise hide the evidence off-screen. The matching
  utterance gets an amber tint + a `cited` chip; if `char_span` is present and
  in range, the exact evidence phrase is wrapped in a `<mark>` so the highlight
  lands on the phrase, not just the utterance. Out-of-range / null spans fall
  back to whole-utterance tint.

So the money shot lands on screen, not just in narration: the clinician hovers
a Plan claim about *metformin 500mg* and the transcript snaps to the exact
clinician utterance that said it, with the phrase itself highlighted.

## What the demo proves (acceptance mapping)

Maps to `execute-plan-v2.md` §6 success criteria:

- [x] Audio → transcript → speaker-attributed dialogue → grounded SOAP note,
      fully local. *(beats 2–3)*
- [x] Every SOAP claim traceable to a transcript span (no ungrounded content).
      *(beat 4 — structurally enforced by `CitationValidator`)*
- [x] Note written back as a valid FHIR `DocumentReference` (R5), linked to
      Patient/Encounter. *(beat 7)*
- [x] Edit-and-approve UI; nothing saved without human sign-off; visible DRAFT
      state. *(beats 3, 5, 6 — the gate is a type, not a step)*
- [x] Eval report: WER, DER, grounding, completeness across the bake-off — no
      LLM-judge. *(see [docs/eval-report.md](eval-report.md))*
