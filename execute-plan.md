# AI Ambient Scribe ⭐ — Execution Plan

> **Tier:** 🟡 Medium · **Est. effort:** 1–2 weeks · **Status:** 🔴 Not started
> **Reuses:** `clinical_core` (LLM, FHIR) · **Feeds into:** B1 (core engine), B2 (documentation agent)
> **Flagship asset — highest market leverage of all 9 projects.**

---

## 1. Overview
Record/upload a doctor–patient consultation, transcribe it, separate speakers, and generate a
structured **SOAP note** (Subjective/Objective/Assessment/Plan), written back as a FHIR
`DocumentReference`. Clinician edits and approves before save (human-in-the-loop). This mirrors the
hottest category in clinical AI (Heidi, Lyrebird, athenaAmbient, Epic Art).

## 2. Why This Project (Market Context)
Ambient scribes are the #1 validated trend of 2026 — major EHRs shipped them and a multicenter study
showed clinician burnout dropping 51.9% → 38.8% after 30 days. Building one proves you can deliver the
exact product the ANZ market is racing to adopt. Hits all three target markets (AU startups, NZ
startups, private clinics).

## 3. Success Criteria
- [ ] Audio in → transcript → speaker-attributed dialogue → structured SOAP note.
- [ ] Note written back as a valid FHIR `DocumentReference` linked to Patient/Encounter.
- [ ] Edit-and-approve UI (nothing saved without human sign-off).
- [ ] Note-quality rubric scored on a sample of consults.

## 4. Tech Stack
Python 3.11+, [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (ASR),
[pyannote.audio](https://github.com/pyannote/pyannote-audio) (diarization), Anthropic SDK (note gen),
FastAPI (backend), a light React or Streamlit front end, `fhir.resources`, pytest.

## 5. Data Source
- Mock consults you record yourself (role-play scripts), or public medical-dialogue datasets, or
  LLM-generated synthetic patient–physician dialogues. **No real PHI.**
- Patient/Encounter context from Synthea.

## 6. Prerequisites & Dependencies
- `clinical_core`. PHI de-identifier (optional, recommended on transcript).
- GPU optional but speeds ASR/diarization; HuggingFace token for pyannote.

## 7. Execution Phases

### Phase 0 — Setup & Audio Harness
**Objectives:** Repo + audio I/O.
**Key tasks:**
- [ ] Init repo/env; install faster-whisper + pyannote; HF token config.
- [ ] Author 5–8 mock consult scripts; record or synthesize audio into `data/consults/`.
**Deliverable:** Sample audio + loaders.
**Acceptance:** Can load and play back sample consults programmatically.

### Phase 1 — Transcription
**Objectives:** Audio → text.
**Key tasks:**
- [ ] Wire faster-whisper; chunking for long audio; timestamps.
- [ ] Basic medical-term sanity check on outputs.
**Deliverable:** `transcribe(audio) -> TranscriptSegments`.
**Acceptance:** Accurate transcript on sample consults; word-level timestamps present.

### Phase 2 — Speaker Diarization
**Objectives:** Who said what.
**Key tasks:**
- [ ] pyannote diarization; align speaker turns to transcript segments.
- [ ] Heuristic role labelling (clinician vs patient) from cues; allow manual override.
**Deliverable:** Speaker-attributed dialogue.
**Acceptance:** Turns correctly attributed on ≥ 80% of sample segments.

### Phase 3 — SOAP Note Generation
**Objectives:** Dialogue → structured note.
**Key tasks:**
- [ ] Define SOAP schema (Pydantic); prompt with "only from transcript" grounding.
- [ ] Generate structured note + extract problems/meds/follow-ups.
- [ ] Faithfulness check (reuse `clinical_core/eval`).
**Deliverable:** `generate_note(dialogue) -> SOAPNote`.
**Acceptance:** Well-formed SOAP notes; faithfulness ≥ 95% on sample.

### Phase 4 — FHIR Write-Back
**Objectives:** Persist as standard health data.
**Key tasks:**
- [ ] Map SOAP note → FHIR `DocumentReference` (+ optional `Composition`); link Patient/Encounter.
- [ ] Validate against FHIR R4.
**Deliverable:** FHIR exporter.
**Acceptance:** Output validates; round-trips through `clinical_core/fhir`.

### Phase 5 — Human-in-the-Loop UI
**Objectives:** Record → review → approve.
**Key tasks:**
- [ ] FastAPI endpoints (upload, transcribe, generate, export).
- [ ] Front end: upload/record → live-ish transcript → editable SOAP note → approve → FHIR export.
- [ ] Visible "draft — requires clinician approval" state.
**Deliverable:** Working app.
**Acceptance:** Full happy path works end-to-end in the UI.

### Phase 6 — Evaluation & Polish
**Objectives:** Quality + presentation.
**Key tasks:**
- [ ] Note-quality rubric (completeness, accuracy, hallucination) scored across sample consults.
- [ ] Latency profiling; README (architecture diagram, demo video), privacy note.
**Deliverable:** Eval report + demo video + README.
**Acceptance:** Rubric report committed; demo video recorded.

## 8. Portfolio Deliverables
Demo **video** (record → note in real time is the money shot), architecture diagram, rubric table.
LinkedIn angle: *"I built an ambient AI scribe end-to-end — audio to FHIR-native SOAP note, with the
clinician in the loop."*

## 9. Risks & Notes
- Diarization is the flakiest part — provide manual speaker correction as a fallback.
- Keep human-approval gate prominent; never imply autonomous charting.
- This is the centrepiece — invest the most polish here.

## 10. Definition of Done
End-to-end audio→FHIR pipeline with approval UI, rubric eval, demo video, README published; note
engine extracted cleanly for reuse in B1/B2.
