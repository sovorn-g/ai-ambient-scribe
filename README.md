# AI Ambient Scribe ⭐

**Fully-local ambient scribe.** A natural doctor–patient conversation →
speaker-attributed transcript → **grounded** SOAP note (every claim cites a
transcript span) → validated FHIR R5 `DocumentReference`. A clinician edits and
approves before anything is saved — the approval gate is enforced by the type
system, not a checkbox.

Zero cloud AI. Runs on a Mac Mini M4, 16GB. No PHI ever — acted/synthetic
public-mock data only.

> The money shot: *two people just talked and a trustworthy, traceable note
> fell out.* The product is the deliverable; the [eval report](docs/eval-report.md)
> is the receipt that proves the stack wasn't picked by vibes.

---

## What it is

A true ambient scribe: record a natural conversation → speaker-attributed
transcript → structured SOAP note grounded to the transcript → written back as a
FHIR `DocumentReference`. Clinician edits and approves before anything is saved.

**"Ambient" means live background capture of natural conversation** (not
dictation, not file-upload). The key distinction that keeps the demo honest:
*input source ≠ processing mode* — the pipeline always processes a **live
ambient audio stream**; the demo feeds a recording *into that live pipeline*
(see [docs/architecture.md](docs/architecture.md)).

## Hard constraints (these drive every decision)

- **Fully local / self-hosted. ZERO cloud AI.** Nothing leaves the machine —
  including note generation. The portfolio point is *"I integrated weak local
  models into something trustworthy,"* not raw model horsepower.
- **Hardware: Mac Mini M4, 16GB.** Caps the note LLM at ~7–8B (q4) or a 4B
  medical model. Sequential load/unload keeps the bake-off within budget.
- **No real PHI, ever.** Acted/synthetic/public-mock data only.
- **Stay a *scribe*, not a *device*.** record→transcribe→summarize is not a
  regulated medical device (AU TGA). Auto-suggesting diagnoses/treatments *not
  raised in the conversation* would flip it into one. → note-gen is **strictly
  grounded to the transcript.**

## The locked stack (one-line reason for each)

| Component | Choice | Why |
|---|---|---|
| **ASR** | `mlx-whisper` large-v3-turbo | Fully offline, trivial on Apple Silicon, multilingual. |
| **Diarization** | sherpa-onnx (pyannote seg + TitaNet-Small) | Provably offline, no HF token, Apache-2.0 — matches the privacy constraint. |
| **Note LLM** | Qwen2.5-7B-Instruct (q4) — *general, not medical* | 2024–25 evidence: general instruct models match or beat medical fine-tunes on *faithful* summarization; some medical models hallucinate more. Apache-2.0, fits 16GB. |
| **Serving** | Ollama (MLX-accelerated) | OpenAI-compatible API → clean pluggable backends; Qwen + MedGemma both packaged. |
| **Schema / API** | Pydantic v2, FastAPI | Constrained/structured output; standard glue. |
| **Frontend** | Next.js (React) | Live mic capture + hover-to-highlight span citations — the two signature features Streamlit can't do. |
| **FHIR** | DocumentReference on R5 via `fhir.resources` | Idiomatic for a clinical note in 2026. |
| **Eval data** | PriMock57 (real mock-consult audio) + ACI-Bench (reference notes) | License-clean, no PHI. |

**Bake-off comparators (note-LLM axis only):** MedGemma-4B, Llama-3.1-8B —
swapped through the same harness to prove the general-vs-medical question on our
own data. See [docs/eval-report.md](docs/eval-report.md).

---

## Quickstart

### 1. Run the test suite (no model loaded)

The fake-path suite runs the whole pipeline through `FakeLLMClient` /
`FakeDialogueExtractor` / `FakeAudioSource` — no model needed to prove the seams
work.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The end-to-end test asserts `generateDraft → approve → approveAndExport` yields a
valid FHIR `DocumentReference`, with `approve()` as the only door.

### 2. Run the real pipeline (CLI smoke, one consult)

```bash
# Ollama daemon + the baseline note model
brew install ollama git-lfs
brew services start ollama        # persistent daemon (survives shell exit)
ollama pull qwen2.5:7b-instruct-q4_K_M

# Python adapters (mlx-whisper, sherpa-onnx, ollama, eval metrics, scispaCy NER)
.venv/bin/pip install -e ".[phase0,phase1,phase3,phase5,dev]"

# scispaCy medical NER model (entity grounding) — note it's ai2-s2, not s3
.venv/bin/pip install "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz"

# sherpa-onnx diarization models (segmentation + speaker embedding)
mkdir -p data/.cache/sherpa-models && cd data/.cache/sherpa-models
curl -sSL -O https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
tar xjf sherpa-onnx-pyannote-segmentation-3-0.tar.bz2 && rm sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
curl -sSL -O https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
cd -

# PriMock57 dataset (CC BY 4.0, 57 mock primary-care consults)
.venv/bin/python scripts/fetch_primock57.py
# → data/primock57/<stem>.{wav,txt,rttm,note.json}  (57 consults, ~950MB)

# One consult through the whole real pipeline
.venv/bin/python scripts/smoke_real_e2e.py
# Add --bakeoff to also run the 3-model bake-off (~10 min on 57 consults).
```

### 3. Run the web UI (the demo surface)

```bash
# Pull the other two bake-off models (optional — UI only needs qwen)
ollama pull medgemma:4b
ollama pull llama3.1:8b-instruct-q4_K_M

# API (FastAPI on :8000) + Web (Next.js on :3000) together
./dev.sh
```

Open http://localhost:3000 → upload a PriMock57 wav (or hit record) → the
pipeline runs → speaker-attributed transcript + editable grounded SOAP appear
under a loud **DRAFT — requires clinician approval** banner → edit a field →
Approve → a FHIR R5 `DocumentReference` is exported. The demo script is in
[docs/demo.md](docs/demo.md).

---

## How faithfulness is framed (read this before the numbers)

The product-level trust mechanism is the **grounding feature** — every SOAP
claim carries a `SpanRef` pointing into the transcript, enforced structurally by
`CitationValidator` (a pure function, no model). The eval report scores it
deterministically: **citation coverage** + **entity grounding** (every
med/dose/condition in the note must trace to the transcript, via scispaCy NER).

Reference metrics (ROUGE vs ACI-Bench) are **completeness only, never labelled
faithfulness.** There is **no LLM-judge anywhere** — a weak local model judging a
weak local model is circular. A 5-note human-eyeball sanity check is the
qualitative backstop. Full NLI / 20-note rubric calibration = stretch, not in
scope. See [docs/eval-report.md](docs/eval-report.md).

## Wiring real adapters via composition

`build_scribe(cfg)` picks real adapters only when the relevant cfg key is set;
otherwise it falls back to the fake/null path (keeps `pytest` green without
models). To drive the real pipeline:

```python
cfg = {
    "transcriber": {"model_id": "mlx-community/whisper-large-v3-turbo"},
    "diarizer": {
        "model_path": "data/.cache/sherpa-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
        "segmentation_model_path": "data/.cache/sherpa-models/sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
        "num_threads": 2, "num_clusters": 2, "threshold": 0.5,
    },
    "llm": {"model_id": "qwen2.5:7b-instruct-q4_K_M"},
    "model_host": {"memory_budget_gb": 16.0},
}
```

For the Phase-4 bake-off, `EvalHarness.run_bakeoff` iterates
`eval.models.DEFAULT_REGISTRY` and calls `model_host.ensure_resident(tag)`
between models so the previous model is evicted before the next loads
(sequential residency within 16GB). WER/DER are model-invariant (locked) and
surface once in the rendered report; grounding + completeness are the per-model
comparison.

---

## Layout

See [docs/architecture.md](docs/architecture.md) for the diagram + deep-module
narrative, and [`design.md`](design.md) for the full vocabulary.

```
scribe/   deep core + thin edges (domain, dialogue, notes, fhir, runtime, app, api, cli)
eval/     second caller — harness, datasets, metrics, bake-off registry, renderer
web/      Next.js adapter over scribe/api
data/     PriMock57, sherpa models (gitignored)
tests/    cross every seam through fakes
scripts/  fetch_primock57, smoke_real_e2e, run_bakeoff_for_report
docs/     architecture, eval-report, demo
plans/    per-phase build plans
```

The frozen public surface is `scribe.app.scribe.Scribe` (two methods:
`generateDraft`, `approveAndExport`). `scribe/composition.py` is the only place
real adapters are wired.
