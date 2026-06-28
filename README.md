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

## Layout

See `design.md` §2 for the full module map. The frozen public surface is
`scribe.app.scribe.Scribe` (two methods: `generateDraft`,
`approveAndExport`). `scribe/composition.py` is the only place real adapters
are wired.
