# AI Ambient Scribe ⭐ — Execution Plan **v2**

> **Tier:** 🟡 Medium · **Status:** 🔴 Not started · **Supersedes:** `execute-plan.md` (left intact)
> **Hill:** *"I can ship a polished end-to-end ML **product**."* (breadth + product sense)
> Depth-of-rigor and FHIR domain credibility are allowed to be merely *competent* — the product is the headline.

This v2 is the output of a grilling pass over v1 + 2026 tech research. It changes the architecture
(fully local), corrects a stale model assumption, and re-orders the work around a **walking skeleton**
so velocity doesn't produce "integrated slop." v1 is kept for diff/history.

---

## 1. What it is
A **true ambient scribe**: record a natural doctor–patient conversation → speaker-attributed
transcript → structured **SOAP note** (grounded to the transcript) → written back as a FHIR
`DocumentReference`. Clinician edits and approves before anything is saved (human-in-the-loop).

**"Ambient" means live background capture of natural conversation** (not dictation, not file-upload).
Key distinction: *input source ≠ processing mode* — the pipeline always processes a **live ambient
audio stream**; the demo feeds a recording *into that live pipeline*, so it stays honest.

## 2. Hard constraints (these drive every decision)
- **Fully local / self-hosted. ZERO cloud AI.** Nothing leaves the machine — including note generation.
  Privacy is a hard constraint; the portfolio point is *"I integrated weak local models into something
  trustworthy,"* not raw model horsepower.
- **Hardware: Mac Mini M4, 16GB.** Caps the note LLM at ~7–8B (q4) or a 4B medical model. Rules out
  14B+/27B/70B. May allow concurrent model loading for short consults; sequential load/unload is the
  fallback (and is needed for the bake-off anyway).
- **No real PHI, ever.** Acted/synthetic/public-mock data only.
- **Stay a *scribe*, not a *device*.** record→transcribe→summarize is not a regulated medical device
  (AU TGA). Auto-suggesting diagnoses/treatments *not raised in the conversation* would flip it into one.
  → note-gen is **strictly grounded to the transcript.** (Aligns with the faithfulness goal anyway.)

## 3. Locked stack (and the one-line reason for each)

| Component | Choice | Why |
|---|---|---|
| **ASR** | `mlx-whisper` **large-v3-turbo** | Fully offline, trivial on Apple Silicon, multilingual. (Swap to **Parakeet-TDT-0.6B-MLX** only if medical-term WER demands it.) |
| **Diarization** | **sherpa-onnx** | *Provably* offline, no HF token, Apache-2.0 — matches the privacy constraint. (pyannote 3.1 = accuracy fallback, download-once-then-offline.) |
| **Note LLM** | **Qwen2.5-7B-Instruct** (q4) — *general, not medical* | 2024–25 evidence: general instruct models **match or beat** medical fine-tunes on *faithful summarization*; some medical models hallucinate **more**. Permissive (Apache-2.0), fits 16GB. |
| **Serving** | **Ollama** (MLX-accelerated) | OpenAI-compatible API → clean pluggable backends; Qwen + MedGemma both packaged. |
| **Note schema / API** | Pydantic v2, FastAPI | Constrained/structured output; standard glue. |
| **Frontend** | **Next.js (React)** | Hill = *polished product*; Streamlit can't do live mic capture or hover-to-highlight span citations — the two signature features. Biggest single build item; lives at Slice 5. |
| **FHIR** | **DocumentReference on R5** via `fhir.resources` (Pydantic v2) | Idiomatic for a clinical note in 2026; R4 dropped in `fhir.resources` v7. |
| **Eval data** | **PriMock57** (real mock-consult audio, license-clean) + **ACI-Bench** (reference notes) | Only license-clean dataset with playable audio; ACI-Bench gives reference notes for faithfulness. No PHI. |

**Bake-off comparators (note-LLM axis only):** MedGemma-4B, Llama-3.1-8B — swapped through the same
harness to *prove* the general-vs-medical question on our own data.

## 4. Build order — walking skeleton first

### Slice 0 — Walking skeleton (build before anything else; ugly on purpose)
The thinnest path that touches **every seam**, so integration risk dies on day one.
- Hardcoded PriMock57 `.wav` (no upload, no record).
- `mlx-whisper` turbo → **raw transcript** (⚠️ *no diarization yet* — keep the flakiest component out of the first run).
- Qwen2.5-7B via Ollama, one plain prompt → SOAP note into a **Pydantic schema**.
- Wrap in **DocumentReference (R5)**, hardcoded Patient/Encounter, validate, write JSON to disk.
- **Approve gate:** CLI `y/n` that gates the FHIR write — human-in-the-loop exists from hour one.
- One script. No UI, no benchmark, no grounding, no eval.

**Acceptance:** the script runs audio → note → validated FHIR → human-gated write, end to end.

### Then, in this order (each deepens a proven seam)
1. **Diarization (sherpa-onnx)** → speaker-labeled dialogue into the LLM. *First* after the skeleton —
   highest technical risk, so it gets maximum time. Target: ≥80% of segments correctly attributed; add
   **manual speaker-correction** as the fallback.
2. **Transcript-span grounding + constrained JSON** — every SOAP claim cites transcript line ranges.
   The single most impressive feature *and* the TGA-safe "never fabricates" story. Core path.
3. **Eval harness (cheap, deterministic, local — no LLM-judge)** — WER (`jiwer`) + DER (`pyannote.metrics`)
   on PriMock57; **grounding** = citation coverage (% of claims with a span) + **entity grounding** (every
   med/dose/condition in the note must trace to the transcript, via scispaCy/medspaCy NER); **completeness**
   = MEDCON/ROUGE vs ACI-Bench reference notes (labelled *completeness*, **never** faithfulness); + a
   **5-note human eyeball** sanity check. (Full NLI / 20-note human-rubric calibration = stretch only.)
4. **Note-LLM bake-off** — run MedGemma-4B / Llama-8B through the same harness → comparison table.
5. **Polished UI (Next.js)** — record/play → live-ish transcript → editable SOAP w/ speaker labels →
   **hover-a-claim-to-highlight-its-transcript-span** → approve → export, with a loud **"DRAFT — requires
   clinician approval"** state. *This is where the "polished" hill is won.* Biggest single time sink;
   if time runs short, the fallback is a **thinner Next.js happy-path** (not a drop back to Streamlit).
6. **Demo video + README + architecture diagram + rubric/eval report.**

### Explicitly deferred until Slice 0 is green
Diarization, grounding/citations, eval harness, bake-off, the real UI, Synthea context, manual
speaker-correction, FHIR `Composition`. None of it before the skeleton runs.

## 5. Benchmark scope (supporting artifact, NOT the headline)
The product is the deliverable; the benchmark is the receipt that proves the stack wasn't picked by vibes.
- **Measure all three axes** (WER, DER, faithfulness) on the primary backend → a number behind every choice.
- **Real bake-off only on the note-LLM** (Qwen-7B vs MedGemma-4B ± Llama-8B) — the only axis where the
  comparison answers an interesting question *and* swapping is free via Ollama.
- **ASR + diarization: locked, not baked off.** Optional 2-way (Parakeet vs whisper-turbo; sherpa vs
  pyannote) only if time survives after the product works.

## 6. Success criteria
- [ ] Audio → transcript → speaker-attributed dialogue → grounded SOAP note, fully local.
- [ ] Every SOAP claim traceable to a transcript span (no ungrounded content).
- [ ] Note written back as a valid FHIR `DocumentReference` (R5), linked to Patient/Encounter.
- [ ] Edit-and-approve UI; nothing saved without human sign-off; visible "draft" state.
- [ ] Eval report: WER, DER, **grounding** (citation + entity-grounding) and **completeness** (MEDCON) across the note-LLM bake-off — no LLM-judge.

## 7. Demo (the money shot)
Play a PriMock57 consult **into the live pipeline** → a complete, speaker-attributed, *grounded* SOAP
note appears → clinician edits one field → approves → FHIR exported. The magic is *"two people just
talked and a trustworthy, traceable note fell out"* — not raw speed (a short processing wait is normal
and expected for ambient scribes).

## 8. Risks & open questions
- **Diarization is the flakiest part** — measure DER on real audio early; manual correction is the fallback.
- **Local 7B hallucinates/omits more** — which is *why* grounding + faithfulness eval + the approval gate
  are the centerpiece, not side dishes.
- **Environment wrangling on M4** (mlx + sherpa-onnx + Ollama together) is the likeliest time sink — not coding.
- **✅ Resolved — faithfulness methodology:** NO local LLM-judge (weak + circular). Keep the **grounding
  feature** (span citations) as the product-level trust mechanism; measure with a **cheap deterministic
  check** — citation coverage + **entity grounding** (note's meds/doses/conditions must trace to the
  transcript, via medical NER) + a **5-note human eyeball**. Reference metrics (ROUGE/MEDCON vs ACI-Bench)
  = *completeness* only, never labelled faithfulness. Full NLI + 20-note rubric calibration = stretch.

## 9. Changelog vs v1
- **Architecture → fully local, zero cloud** (v1 used cloud Claude for note-gen).
- **Note LLM → general model (Qwen2.5-7B), not a medical fine-tune** — evidence says medical fine-tunes
  don't help faithful summarization and can hurt. Medical models demoted to bake-off comparators.
- **Diarization → sherpa-onnx** (provably offline) over pyannote default; **ASR → mlx-whisper/Parakeet**
  over faster-whisper (Apple-Silicon native).
- **FHIR → R5** (v1 said R4).
- **Work re-ordered around a walking skeleton** with an explicit deferral list (v1 was phase-by-phase,
  breadth-first).
- **Benchmark scoped down** to a note-LLM bake-off + single-backend measurement (not an all-axis bake-off).
- Added **TGA medical-device boundary** and **PriMock57/ACI-Bench** as the no-PHI data spine.

## 10. Timeline, definition of done & scope freeze
**Target: a *complete* portfolio piece (all §6 criteria met) in ~4 weeks** — single builder + AI codegen.
This is **not** an MVP/cut-down; there is no "minimum publishable cut" — the commitment is to finish
Slices 0–6. The slice order is the path to complete (it keeps the build always-shippable), not a fallback ladder.

Indicative cadence (sequencing, not a contract):
- **Week 1:** Slice 0 walking skeleton → Slice 1 diarization (riskiest, front-loaded so it gets the most time).
- **Week 2:** Slice 2 span-grounding + constrained output → Slice 3 cheap deterministic eval harness.
- **Week 3:** Slice 4 note-LLM bake-off → start Slice 5 Next.js UI.
- **Week 4:** finish Slice 5 polished UI → Slice 6 demo video + README + architecture diagram + eval report.

**🔒 SCOPE FREEZE:** v2 above is the locked scope. The real threat to the 1-month finish is *mid-build
scope creep*, not the estimate. Any new idea during the build goes to a **v3 backlog**, not this month.
Named **stretch items stay OUT** unless a slice finishes early: full NLI / 20-note rubric calibration,
ASR/diarization 2-way bake-off, Synthea patient context, FHIR `Composition`, manual speaker-correction UI,
streaming/live transcript display, multilingual/accent handling, a second specialty.
