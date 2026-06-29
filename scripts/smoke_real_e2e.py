"""Real end-to-end smoke — exercises every adapter against real models + audio.

Unlike the pytest suite (which runs through fakes), this script wires the REAL
adapters and runs one PriMock57 consultation through the whole pipeline:

  wav → mlx-whisper ASR → sherpa-onnx diarization → align → label_roles
      → OllamaLLMClient (qwen2.5:7b) → GroundedNote → approve → FHIR export
      → EvalHarness (WER / DER / grounding / completeness)

Then runs the Phase-4 bake-off across all three Ollama tags so we can see real
per-model numbers.

Exit code 0 = every step succeeded and produced sane output.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scribe.app.approval import approve
from scribe.app.drafts import InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.dialogue import DialogueExtractor
from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer
from scribe.dialogue.transcriber.mlx_whisper import MlxWhisperTranscriber
from scribe.domain.types import EditedDraft, PatientContext
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.notes.llm.ollama import OllamaLLMClient
from scribe.runtime.model_host import ModelHost
from eval.datasets.primock57 import PriMock57Dataset
from eval.harness import EvalHarness
from eval.models import DEFAULT_REGISTRY
from eval.report import render_bakeoff_report

SHERPA_DIR = ROOT / "data" / ".cache" / "sherpa-models"
SEG_MODEL = str(SHERPA_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx")
EMB_MODEL = str(SHERPA_DIR / "nemo_en_titanet_small.onnx")


def _ok(label: str) -> None:
    print(f"  ✓ {label}")


def _section(title: str) -> None:
    print(f"\n── {title} ────────────────────────────────────────────")


def _build_scribe(ollama_tag: str) -> Scribe:
    transcriber = MlxWhisperTranscriber(model_id="mlx-community/whisper-large-v3-turbo")
    diarizer = SherpaOnnxDiarizer(
        model_path=EMB_MODEL,
        segmentation_model_path=SEG_MODEL,
        num_threads=2, num_clusters=2, threshold=0.5,
    )
    llm = OllamaLLMClient(model_id=ollama_tag)
    return Scribe(
        dialogue_extractor=DialogueExtractor(transcriber, diarizer),
        note_generator=NoteGenerator(llm),
        fhir_exporter=FhirExporter(),
        draft_store=InMemoryDraftStore(),
        model_host=ModelHost(),
    )


def main() -> int:
    dataset = PriMock57Dataset(data_dir=str(ROOT / "data" / "primock57"))
    items = dataset.items()
    if not items:
        print("[fatal] no PriMock57 items — run scripts/fetch_primock57.py first")
        return 2
    item = items[0]
    print(f"[setup] item={item.item_id}"
          f"  ref_transcript={len(item.reference_transcript or '')} chars"
          f"  ref_note={len(item.reference_note or '')} chars")

    _section("Build real Scribe")
    scribe = _build_scribe("qwen2.5:7b-instruct-q4_K_M")
    print(f"  transcriber={scribe._dialogue_extractor.transcriber_id}")
    print(f"  diarizer={scribe._dialogue_extractor.diarizer_id}")
    print(f"  llm={scribe._note_generator.llm_id}")
    _ok("real adapters wired")

    _section("1. ASR (mlx-whisper large-v3-turbo)")
    t0 = time.time()
    segs = scribe._dialogue_extractor._transcriber.transcribe(item.audio)
    print(f"  {len(segs)} segments in {time.time()-t0:.1f}s")
    for s in segs[:3]:
        print(f"    [{s.time_span.start:.2f}-{s.time_span.end:.2f}] {s.text[:60]!r}")
    assert len(segs) > 0, "ASR produced no segments"
    _ok(f"transcribed {len(segs)} segments")

    _section("2. Diarization (sherpa-onnx pyannote + TitaNet-Small)")
    t0 = time.time()
    turns = scribe._dialogue_extractor._diarizer.diarize(item.audio)
    print(f"  {len(turns)} turns in {time.time()-t0:.1f}s")
    spks = {t.speaker_id for t in turns}
    print(f"  speakers detected: {sorted(spks)}")
    for t in turns[:3]:
        print(f"    [{t.time_span.start:.2f}-{t.time_span.end:.2f}] {t.speaker_id}")
    assert len(turns) > 0, "diarization produced no turns"
    _ok(f"{len(turns)} turns, {len(spks)} speakers")

    _section("3. DialogueExtractor.extract (align + label_roles)")
    t0 = time.time()
    dialogue = scribe._dialogue_extractor.extract(item.audio)
    print(f"  {len(dialogue.utterances)} utterances in {time.time()-t0:.1f}s")
    for u in dialogue.utterances[:4]:
        print(f"    {u.id} [{u.time_span.start:.2f}-{u.time_span.end:.2f}] "
              f"{u.role.name:9} spk={u.speaker_id}  {u.text[:50]!r}")
    assert len(dialogue.utterances) > 0
    _ok(f"aligned + labelled {len(dialogue.utterances)} utterances")

    _section("4. Note generation (Ollama qwen2.5:7b) → GroundedNote")
    ctx = PatientContext(patient_ref="Patient/primock57-1",
                         encounter_ref="Encounter/primock57-1")
    draft_cache = ROOT / "data" / ".cache" / "debug_draft.json"
    if "--cache-draft" in sys.argv and draft_cache.exists():
        from scribe.domain.types import Draft
        draft = Draft.model_validate_json(draft_cache.read_text())
        print(f"  [cache] loaded draft from {draft_cache}")
    else:
        t0 = time.time()
        draft = scribe.generateDraft(item.audio, ctx)
        print(f"  draft in {time.time()-t0:.1f}s")
        draft_cache.parent.mkdir(parents=True, exist_ok=True)
        draft_cache.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    print(f"  subjective claims: {len(draft.note.subjective)}")
    print(f"  objective claims:  {len(draft.note.objective)}")
    print(f"  assessment claims: {len(draft.note.assessment)}")
    print(f"  plan claims:       {len(draft.note.plan)}")
    total_claims = (len(draft.note.subjective) + len(draft.note.objective)
                    + len(draft.note.assessment) + len(draft.note.plan))
    assert total_claims > 0, "note has no claims"
    _ok(f"GroundedNote with {total_claims} claims (all structurally grounded)")

    _section("5. Approve → FHIR export")
    edited = EditedDraft(id=draft.id, ctx=ctx, dialogue=draft.dialogue,
                         note=draft.note, provenance=draft.provenance)
    from scribe.domain.types import Approver
    approved = approve(edited, approver=Approver(name="smoke-test"))
    doc = scribe._fhir_exporter.toDocumentReference(approved, ctx)
    print(f"  FHIR DocumentReference status={doc.resource.get('status')}")
    assert doc.resource.get("status") == "current"
    _ok("FHIR R5 DocumentReference produced")

    _section("6. EvalHarness — WER / DER / grounding / completeness")
    try:
        from eval.metrics.grounding import load_scispacy_nlp
        nlp = load_scispacy_nlp()
        print(f"  scispacy NER: {'loaded' if nlp else 'disabled'}")
    except Exception as e:
        print(f"  scispacy NER: unavailable ({e})")
        nlp = None

    harness = EvalHarness(scribe, ctx, nlp=nlp)
    report = harness.run(dataset)
    print(f"  metrics components: {sorted(report.metrics.keys())}")
    for comp, scores in report.metrics.items():
        pretty = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in scores.items()}
        print(f"    {comp}: {pretty}")
    _ok("EvalHarness produced real metrics on real audio")

    if "--bakeoff" not in sys.argv:
        print("\nCORE PIPELINE SMOKE PASSED (steps 1-6)")
        print("  Run with --bakeoff to also exercise the 3-model bake-off (~10 min)")
        return 0

    _section("7. Phase-4 bake-off across 3 models")
    print("  (evicts + reloads each model — re-runs full pipeline per model, ~10 min)")

    def _loader(tag: str) -> None:
        subprocess.run(["ollama", "pull", tag], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _evictor(tag: str) -> None:
        # keep_alive=0 tells Ollama to unload the model from GPU/RAM immediately.
        import httpx
        try:
            httpx.post("http://localhost:11434/api/generate",
                       json={"model": tag, "keep_alive": 0}, timeout=30)
        except Exception:
            pass  # eviction is best-effort; bakeoff continues if Ollama is slow

    host = ModelHost(loader=_loader, evictor=_evictor)

    t0 = time.time()
    bake = harness.run_bakeoff(
        dataset, DEFAULT_REGISTRY,
        build_scribe_for_model=lambda spec: _build_scribe(spec.ollama_tag),
        model_host=host,
    )
    print(f"  bake-off in {time.time()-t0:.1f}s, evictions={host.evictions}")
    for mid, sub in bake.per_model.items():
        g = sub.metrics.get("grounding", {}).get("citation_coverage")
        c = sub.metrics.get("completeness", {}).get("rouge1")
        print(f"    {mid:18} grounding.cov={g}  completeness.rouge1={c}")
    _ok(f"bake-off produced {len(bake.per_model)} per-model reports")

    _section("Render bake-off report")
    out = render_bakeoff_report(bake)
    print(out[:700])
    print("  ... (truncated) ...")
    _ok("renderer produced markdown")

    print("\nALL REAL-PATH SMOKE STEPS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
