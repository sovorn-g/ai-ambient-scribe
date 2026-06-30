# Phase 7 — Ambient Listening Mode (live capture, final batch note)

> **Goal:** make the product honestly ambient without turning it into a full realtime clinical-ops
> platform. A clinician clicks the round **Record** dial, the browser captures a natural conversation
> in the background while a voice-reactive listening dial pulses on screen, and **End consultation**
> runs the existing high-quality batch pipeline on the **full** captured recording to produce the final
> grounded SOAP note + FHIR export.
>
> **Positioning:** *ambient capture is live; final clinical artifacts are batch, grounded, and
> clinician-approved. The LLM never sees partial audio.*
>
> **Depends on:** Phases 1–6 merged + green. The existing batch path is the source of truth.
> **Blocks:** final demo video / portfolio polish. **Parallel-safe with:** mostly no — touches API,
> frontend state, docs, and composition wiring. Run as a solo feature slice.

## Context for a cold agent

Read `design.md §3` (`Scribe` facade), `§4` (approval gate), `§5` (`AudioSource` seam),
`plans/phase-5-ui.md`, and `docs/architecture.md` before coding.

The current product is **batch** despite the ambient name: upload a file, wait, receive a final
transcript + SOAP note. Phase 7 makes the *input experience* ambient while preserving the quality story:

- Live mode captures audio continuously in the browser.
- Audio chunks stream to FastAPI over WebSocket.
- The UI during recording is a round voice-reactive listening dial — **no provisional transcript**.
- On **End consultation**, the server writes the full captured audio to a WAV file and calls the
  existing `Scribe.generateDraft(audio, ctx)` path on the complete recording.
- Final transcript, grounded SOAP citations, edit/review, approval, and FHIR export remain exactly the
  existing batch pipeline.

The final LLM feed always waits for the complete recording. Partial audio is never sent to note
generation.

## Non-goals / scope guardrails

This phase is **not** a full realtime ambient clinical platform.

Out of scope:

- Incremental SOAP generation while the consultation is still running.
- Provisional / partial transcript displayed during recording.
- Treating any in-progress chunk as clinically authoritative.
- Real-time diarization as a hard requirement.
- Replacing MLX-Whisper / sherpa / Ollama stack.
- Changing `Scribe.generateDraft`, `approveAndExport`, `GroundedNote`, or the approval gate.
- Cloud ASR / Web Speech API / browser-vendor transcription. Zero cloud AI remains mandatory.
- A separate replay-as-live demo mode (removed in this revision — see "Product behavior").

Acceptable compromise:

- The UI shows only the listening dial during recording (no preview text). The dial's voice-reactive
  waveform is the ambient feedback that the system is listening.
- Background chunk transcription for very long sessions is a **future extension**, not current
  behavior. If added later, it would transcribe windows in the background while the dial keeps
  running visually — but the final LLM feed would still wait for the complete recording.

## Product behavior

### Mode 1 — Ambient live listening (new, default)

1. User clicks the round **Record** dial.
2. Browser requests microphone permission with `navigator.mediaDevices.getUserMedia`.
3. UI enters a listening state: the dial flips to a clinical-blue circle with a red live ring, pulsing
   outer rings, an animated waveform that reacts to voice RMS/peak, and an elapsed timer.
4. Browser encodes mono PCM16 chunks and streams them over WebSocket.
5. Backend appends chunks to an `AmbientSession` buffer. No preview ASR is run.
6. User clicks **■ End consultation**.
7. Backend writes the full WAV file and calls the existing batch `Scribe.generateDraft` path on the
   complete recording.
8. UI transitions to the final speaker-attributed transcript + grounded SOAP note under the DRAFT
   banner.
9. Existing edit / citation navigator / approval / FHIR export flow continues unchanged.

### Mode 2 — Existing batch upload (keep)

Current upload flow remains available:

1. Upload `.wav` / supported audio file.
2. Run batch pipeline.
3. Review grounded SOAP note.
4. Approve → FHIR `DocumentReference`.

This is still useful for debugging and benchmark replay, and as a fallback when no mic is available.

### Removed: Replay-as-live mode

An earlier revision of this plan scoped a "Replay recording as live" demo mode that fed a PriMock57
`.wav` through the same live WebSocket as mic capture. It was removed in this revision to keep the
product surface focused. The same demo outcome (a known recording through the final pipeline) is
already covered by **Mode 2 — Upload recording**.

## Architecture

Keep the API thin. Put stateful ambient-session behavior behind an app-layer service rather than inside
FastAPI endpoint functions.

Proposed modules:

```
scribe/app/ambient.py                  # AmbientSessionService: session state, buffering, finalize→Draft
scribe/runtime/live_audio.py           # PCM16 chunk handling, WAV writer
scribe/api/app.py                      # WebSocket + thin calls into AmbientSessionService
scribe/composition.py                  # wire AmbientSessionService with existing Scribe (no preview transcriber)
web/components/AmbientRecorder.tsx     # round listening dial, voice-reactive waveform, Start/Stop/Cancel
web/lib/liveAudio.ts                   # getUserMedia, PCM16 encoding/chunking, LevelSample
web/lib/api.ts                         # WebSocket client helpers / ambient endpoint types
web/app/page.tsx                       # mode switch: live vs upload; final Draft state reused

tests/test_ambient.py                  # session service + websocket tests with fake scribe
```

### New app-layer service

`AmbientSessionService` should own all nontrivial state:

```python
class AmbientSessionService:
    def start_session(ctx: PatientContext, sample_rate: int = 16000) -> AmbientSession
    async def append_audio(session_id: str, pcm16: bytes) -> list[AmbientEvent]
    async def finalize(session_id: str) -> Draft
    def cancel(session_id: str) -> None
```

Implementation detail can differ, but the shape should preserve these responsibilities:

- Accumulate the **complete** audio for final batch generation.
- Write final audio as a temp `.wav` file.
- Call `Scribe.generateDraft(Audio(source="stream", path=final_wav_path), ctx)` on finalize.
- Return a normal `Draft` so the existing UI/review/approve path can be reused.
- No preview cursor, no preview ASR, no `partial_transcript` events. (Background chunk transcription
  is a future extension; if added, it must not feed the final LLM until the recording is complete.)

### WebSocket protocol

Use a simple event protocol. Keep it explicit and debuggable.

Client → server JSON:

```json
{ "type": "start", "patient_ref": "Patient/demo", "encounter_ref": "Encounter/demo", "sample_rate": 16000 }
{ "type": "stop" }
{ "type": "cancel" }
```

Client → server binary:

- Raw PCM16 little-endian mono chunks, preferably 16 kHz.
- Chunk duration target: 250–1000 ms.

Server → client JSON:

```json
{ "type": "session_started", "session_id": "..." }
{ "type": "listening", "seconds": 12.3, "bytes_received": 393216 }
{ "type": "finalizing" }
{ "type": "draft_ready", "draft": { /* existing DraftResponse shape */ } }
{ "type": "error", "message": "..." }
```

Do not stream SOAP claims or partial transcripts over this socket in Phase 7. The final `draft_ready`
payload reuses the existing `DraftResponse` shape.

### Audio format decision

Prefer PCM16 over WebSocket instead of `MediaRecorder` blobs.

Reason: `MediaRecorder` yields browser-dependent containers (`webm/opus`, `mp4`, etc.), which may require
ffmpeg/container handling before MLX-Whisper can read them. PCM16 chunks are boring and deterministic.

Frontend approach:

- `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })`.
- `AudioContext` / `AudioWorklet` (or `ScriptProcessorNode` fallback) reads float samples.
- Resample to 16 kHz mono if the device runs at 44.1/48 kHz.
- Convert to PCM16 little-endian.
- Send binary chunks over WebSocket.
- Keep an RMS/peak `LevelSample` derived from the same PCM samples for the listening dial.

Backend approach:

- Append PCM16 to a session buffer.
- On finalize, write a valid WAV header + PCM data to a temp file.
- The batch pipeline reads the full WAV.

## Files I OWN (create/edit)

```
scribe/app/ambient.py
scribe/runtime/live_audio.py
scribe/api/app.py
scribe/api/schemas.py
scribe/composition.py                 # only ambient-service wiring; do not rewrite Scribe construction
web/app/page.tsx
web/components/AmbientRecorder.tsx
web/lib/api.ts
web/lib/liveAudio.ts
tests/test_ambient.py
docs/demo.md
README.md
docs/architecture.md
```

## Frozen — do not touch

- `scribe/app/scribe.py` public methods and approval gate semantics.
- `scribe/app/approval.py` and `scribe/fhir/**` approval/export logic.
- `scribe/domain/types.py` unless a tiny additive enum/string for `Audio.source` is unavoidable. Prefer no domain changes.
- `scribe/notes/**` note generation and citation validation.
- `eval/**` metrics/harness.

## Implementation tasks

### 7a — Backend session skeleton

1. Add `AmbientSessionService` with in-memory session registry.
2. Add `LiveAudioBuffer` / WAV writer for PCM16 chunks.
3. Add FastAPI WebSocket endpoint, e.g. `/ambient/ws`.
4. Handle `start`, binary chunks, `stop`, `cancel`, disconnect cleanup.
5. On `stop`, write final WAV and call existing `Scribe.generateDraft`.
6. Return existing `DraftResponse` through a `draft_ready` event.

### 7b — Frontend live recorder

1. Add a two-tab mode switch: **Live listening** (default) vs **Upload recording**.
2. Implement `AmbientRecorder` with a round listening dial:
   - mic permission flow,
   - idle / requesting / listening / finalizing states,
   - pulsing outer rings while listening,
   - red live ring that scales with RMS,
   - animated waveform bars driven by `LevelSample` (RMS + peak), centered voice-print envelope,
   - elapsed timer,
   - WebSocket lifecycle,
   - Start / End / Cancel controls,
   - peak indicator dot,
   - reduced-motion-safe fallback (`motion-reduce:animate-none`).
3. On `draft_ready`, reuse the existing final review UI state (`draft`, `step=review`) so SOAP editor,
   citation navigator, approval, and FHIR export continue unchanged.
4. Handle errors gracefully: mic denied, socket closed, backend error, model not ready.

### 7c — Docs and positioning

1. Update README so the ambient claim is now literal: live capture + final batch note (two input modes).
2. Update `docs/architecture.md` to show `AmbientSessionService` and clarify:
   - no provisional transcript,
   - final note uses batch pipeline on the full recording,
   - approval gate unchanged,
   - background chunk transcription is a future extension only.
3. Update `docs/demo.md` with a new demo beat sequence:
   - Start listening (round dial),
   - hold the conversation (waveform reacts),
   - End consultation,
   - final grounded SOAP appears,
   - click `◀ 1/X ▶` to prove citations.

## Tests

### Python

- `tests/test_ambient.py`:
  - start session returns id and initial listening event,
  - PCM chunks append to buffer,
  - stop/finalize writes a WAV-like file and calls fake `Scribe.generateDraft`,
  - final result is a normal DRAFT, not approved/exported,
  - cancel/disconnect cleans session state,
  - invalid message order returns error (chunk before start, stop unknown session).
- WebSocket integration test with FastAPI `TestClient.websocket_connect` and fake services.
- Existing full suite must remain green.

### Frontend

- `tsc --noEmit` clean.
- Minimal component/unit test if tooling exists; otherwise manual smoke documented:
  - mic permission denied,
  - start/stop happy path,
  - final draft reuses SOAP/citation/approve UI.

## Manual verification

1. `./dev.sh`.
2. Open `http://localhost:3000`.
3. Click the round **Record** dial and speak for ~20 seconds.
4. Confirm the dial pulses and the waveform reacts to your voice; the timer ticks.
5. Click **■ End consultation**.
6. Confirm final transcript + SOAP note appears under the DRAFT banner.
7. Click `◀ 1/X ▶` on a multi-cite claim and verify transcript scroll/highlight.
8. Edit one claim, approve, verify FHIR `DocumentReference` renders.
9. Switch to **Upload recording** and verify the original batch path still works.

## Acceptance

- [ ] User can start/stop a live mic session from the browser via a round listening dial.
- [ ] Audio streams to backend over WebSocket as local PCM chunks; no cloud transcription/API.
- [ ] The listening dial is voice-reactive (waveform jumps with RMS/peak) and shows elapsed time.
- [ ] End consultation runs the existing high-quality batch pipeline on the full captured audio.
- [ ] Final UI is the same grounded review flow: final transcript, SOAP claims, `◀ 1/X ▶` citation navigation, edit, approval, FHIR export.
- [ ] Existing upload/batch path still works.
- [ ] Approval gate unchanged: no `DocumentReference` without clinician approval.
- [ ] Tests green; `tsc --noEmit` green.
- [ ] README / architecture / demo docs updated to explain live capture vs final batch truth.

## Merge checklist

- [ ] API endpoint functions remain thin; stateful live behavior lives in `AmbientSessionService`.
- [ ] No changes to `Scribe.generateDraft` / `approveAndExport` signatures.
- [ ] No cloud services introduced.
- [ ] No provisional transcript is rendered; the LLM never sees partial audio.
- [ ] Batch eval numbers are not reused to claim live accuracy.
- [ ] Replay-as-live mode is removed (no longer in scope).

## UI Design Guide — Ambient Listening Mode

> The signature UI element is a **round listening dial** with a voice-reactive waveform. This is the
> one place a more "consumer" visual is acceptable: it directly visualizes the live audio signal,
> which is technically honest and the ambient promise made visible.

### Existing design system (do not change)

| Token      | Value     | Role                             |
|------------|-----------|----------------------------------|
| `vellum`   | #F4F2EB   | page background                  |
| `nuit`     | #16162A   | primary text, dark surfaces      |
| `dusty`    | #7A6E60   | secondary text, muted labels     |
| `clinical` | #1B4D82   | primary action blue, CTA buttons |
| `ruled`    | #E6E1D5   | borders, dividers                |
| `alert`    | #B91C1C   | error, DRAFT stamp               |
| emerald    | Tailwind  | success states only              |
| amber      | Tailwind  | citation highlights only         |

Typography: `font-grotesk` (labels, UI), `font-lora` (transcript body), `font-mono` (timestamps,
metadata). `label-caps` utility class (10px, 700, uppercase, 0.14em tracking, `text-dusty`) is the
section header convention.

### Mode selector

A two-tab toggle above the patient context card. Underline-style tabs, not a pill toggle.

- Both tabs: `label-caps px-3 py-1.5 rounded-t border-b-2`
- Active: `border-clinical text-nuit`
- Inactive: `border-transparent text-dusty/60 hover:text-dusty`

Tabs (left to right): **Live listening**, **Upload recording**.

### The round listening dial (signature element)

A 200px core circle centered in a 260px interaction area. Four visual states:

1. **Idle** — `bg-vellum border-2 border-clinical/40 text-clinical`, with a `●` glyph and `Record`
   label inside. Hover: `hover:bg-clinical/5`.
2. **Requesting** — `bg-ruled/30`, with a small spinner and `Requesting mic…` label.
3. **Listening** — `bg-clinical text-white`:
   - Outer pulse rings (two `<span>`s, `border-clinical/30` / `border-clinical/20`, animated with the
     `ambient-pulse` keyframe at 2.4s, second ring staggered 0.8s).
   - Red live ring (`border-2 border-red-500/80`) whose `scale` follows `1 + rms * 0.18`, transition
     90ms linear.
   - Inside the core: a row of N (e.g. 28) vertical waveform bars driven by an envelope × RMS × phase
     synthesis (no FFT needed — a single RMS number is enough for a lively voice print).
   - Below the bars: an elapsed timer `font-mono text-sm tabular-nums tracking-widest`.
   - A small peak-indicator dot top-right of the interaction area, opacity tied to peak level.
4. **Finalizing** — `bg-clinical/70 text-white`, waveform bars dimmed to ~0.45 opacity, a `finalising…`
   label below.

The `ambient-pulse` keyframe:

```css
@keyframes ambient-pulse {
  0%   { transform: scale(1);    opacity: 0.6; }
  70%  { transform: scale(1.25); opacity: 0;   }
  100% { transform: scale(1.25); opacity: 0;   }
}
```

All animations must respect `motion-reduce:animate-none`. The dial is decorative; the elapsed timer
conveys duration for screen readers. Real buttons (Start / End / cancel) sit **below** the dial and
are keyboard-focusable.

### Bottom controls

- **Idle**: `[● Start listening]` — `bg-clinical text-white rounded-full`.
- **Listening**: `[■ End consultation]` (`bg-emerald-600 text-white rounded-full`) + a `cancel` text
  button (`label-caps text-dusty hover:text-alert`).
- **Finalizing**: a static `running batch pipeline…` label, no buttons.

### On draft_ready — transition to final review

When the WebSocket delivers `draft_ready`, set `draft` state and advance to `step="review"`. From
that point, the existing UI is **completely unchanged**: final transcript in `TranscriptPane`, SOAP
editor, citation navigator, approve section, FHIR export. The dial card is discarded.

### What NOT to do

- Do not render a provisional transcript. The dial is the only live feedback.
- Do not feed partial audio to the note LLM.
- Do not show a SOAP preview during recording.
- Do not use gradient fills on any new card or surface.
- Do not introduce a new accent color for the live mode. `clinical` blue for the dial, red for the
  live ring, emerald for the stop action, and existing tokens for everything else.
- Retain `label-caps` for every new section header.

## Status

Implemented (this revision): live listening dial + final batch pipeline, upload recording retained,
replay-as-live and provisional transcript removed.
