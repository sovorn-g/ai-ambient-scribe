# AI Ambient Scribe ⭐

Fully-local ambient scribe: a natural doctor–patient conversation →
speaker-attributed transcript → grounded SOAP note → validated FHIR R5
`DocumentReference`. Clinician edits and approves before anything is saved
(human-in-the-loop, enforced structurally — see `design.md` §4).

Zero cloud AI. Built to run on a Mac Mini M4, 16GB.

## Phase 0 — walking skeleton

The thinnest end-to-end path that touches every seam (see
`plans/phase-0-skeleton.md`): hardcoded wav → raw transcript → SOAP note →
validated FHIR `DocumentReference` → human-gated write.

### Run the tests (no model loaded)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The end-to-end test runs the whole pipeline through fakes — no Ollama, no
mlx-whisper, no mic — and asserts `generateDraft → approve → approveAndExport`
yields a valid FHIR `DocumentReference`, with `approve()` as the only door.

### Run the real-path smoke (needs Ollama + mlx-whisper)

1. Start Ollama and pull the model:
   ```bash
   ollama serve &
   ollama pull qwen2.5:7b-instruct-q4_K_M
   ```
2. Install the Phase-0 extras and run the CLI against a PriMock57 wav:
   ```bash
   .venv/bin/pip install -e ".[phase0]"
   .venv/bin/python -m scribe.cli.main --audio data/primock57/sample.wav
   ```
3. Approve at the `y/n` prompt; FHIR JSON is written to
   `out/documentreference.json`.

## Real-path setup (every adapter, every model)

The fake-path test suite runs the whole pipeline through `FakeLLMClient` /
`FakeDialogueExtractor` / `FakeAudioSource` — no model is needed to prove the
seams work. To run the **real** adapters (ASR, diarization, note-LLM, grounding
NER) and the Phase-4 bake-off on real PriMock57 audio:

```bash
# 1. Ollama binary + daemon + the three bake-off models (~13GB of pulls)
brew install ollama git-lfs
brew services start ollama        # persistent daemon (survives shell exit)
ollama pull qwen2.5:7b-instruct-q4_K_M   # baseline (4.7GB)
ollama pull medgemma:4b                   # medical fine-tune (3.3GB)
ollama pull llama3.1:8b-instruct-q4_K_M  # size control (4.9GB)

# 2. Python adapters (mlx-whisper, sherpa-onnx, ollama client, eval metrics,
#    scispacy/medspacy NER, rouge-score)
.venv/bin/pip install -e ".[phase0,phase1,phase3,dev]"

# 3. scispaCy medical NER model (entity grounding) — note it's ai2-s2, not s3
.venv/bin/pip install "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz"

# 4. sherpa-onnx diarization models (segmentation + speaker embedding)
mkdir -p data/.cache/sherpa-models && cd data/.cache/sherpa-models
curl -sSL -O https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
tar xjf sherpa-onnx-pyannote-segmentation-3-0.tar.bz2 && rm sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
curl -sSL -O https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
cd -

# 5. PriMock57 dataset (CC BY 4.0, 57 mock primary-care consults)
.venv/bin/python scripts/fetch_primock57.py
# → data/primock57/<stem>.{wav,txt,rttm,note.json}  (57 consultations, ~950MB)
```

### Wiring the real adapters via composition

`build_scribe(cfg)` picks real adapters only when the relevant cfg key is set;
otherwise it falls back to the fake/null path (keeps `pytest` green without
models). To drive the real pipeline, pass a cfg like:

```python
cfg = {
    "transcriber": {"model_id": "mlx-community/whisper-large-v3-turbo"},
    "diarizer": {
        "model_path": "data/.cache/sherpa-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
        "segmentation_model_path": "data/.cache/sherpa-models/sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
        "num_threads": 2, "num_clusters": 2, "threshold": 0.5,
    },
    "llm": {"model_id": "qwen2.5:7b-instruct-q4_K_M"},
    # model_host.loader / evictor get real ollama pull/unload for the bake-off
    "model_host": {"memory_budget_gb": 16.0},
}
```

For the Phase-4 bake-off, `EvalHarness.run_bakeoff` iterates
`eval.models.DEFAULT_REGISTRY` and calls `model_host.ensure_resident(tag)`
between models so the previous model is evicted before the next loads
(sequential residency within 16GB). The WER/DER axes are model-invariant
(locked) and surface once in the rendered report; grounding + completeness
are the per-model comparison.

## Layout

See `design.md` §2 for the full module map. The frozen public surface is
`scribe.app.scribe.Scribe` (two methods: `generateDraft`,
`approveAndExport`). `scribe/composition.py` is the only place real adapters
are wired.
