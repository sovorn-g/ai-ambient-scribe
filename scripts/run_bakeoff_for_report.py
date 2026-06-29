"""Run the Phase-4 note-LLM bake-off on a PriMock57 subset and persist results.

This is a docs-generation helper for Phase 6: it runs the *existing* eval
harness (no source edits to scribe/** or eval/**) over the first N PriMock57
consultations across all three registry models, then writes:

  * data/.cache/bakeoff_report.json   — raw per-model metrics (for re-rendering)
  * data/.cache/bakeoff_report.md     — the harness-rendered markdown table

Real adapters only: mlx-whisper ASR, sherpa-onnx diarization, Ollama note-LLM.
Expects `ollama serve` running and the three tags pulled (see README).

Usage:
    .venv/bin/python scripts/run_bakeoff_for_report.py [--n 8]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scribe.app.drafts import InMemoryDraftStore
from scribe.app.scribe import Scribe
from scribe.dialogue import DialogueExtractor
from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer
from scribe.dialogue.transcriber.mlx_whisper import MlxWhisperTranscriber
from scribe.domain.types import PatientContext
from scribe.fhir import FhirExporter
from scribe.notes import NoteGenerator
from scribe.notes.llm.ollama import OllamaLLMClient
from scribe.runtime.model_host import ModelHost
from eval.datasets.primock57 import PriMock57Dataset
from eval.datasets.base import Dataset
from eval.harness import EvalHarness
from eval.models import DEFAULT_REGISTRY
from eval.report import render_bakeoff_report

SHERPA_DIR = ROOT / "data" / ".cache" / "sherpa-models"
SEG_MODEL = str(SHERPA_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx")
EMB_MODEL = str(SHERPA_DIR / "nemo_en_titanet_small.onnx")


class _SubsetDataset(Dataset):
    """Wrap PriMock57 and expose only the first N items."""

    def __init__(self, inner: Dataset, n: int) -> None:
        self._inner = inner
        self._items = inner.items()[:n]

    @property
    def name(self) -> str:
        return f"{self._inner.name}[:n]"

    def items(self):
        return self._items


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


def _loader(tag: str) -> None:
    subprocess.run(["ollama", "pull", tag], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _evictor(tag: str) -> None:
    import httpx
    try:
        httpx.post("http://localhost:11434/api/generate",
                   json={"model": tag, "keep_alive": 0}, timeout=30)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8,
                    help="number of PriMock57 consultations to evaluate (default 8)")
    ap.add_argument("--out-dir", type=str, default=str(ROOT / "data" / ".cache"))
    args = ap.parse_args()

    full = PriMock57Dataset(data_dir=str(ROOT / "data" / "primock57"))
    items = full.items()
    if not items:
        print("[fatal] no PriMock57 items — run scripts/fetch_primock57.py first")
        return 2
    n = max(1, min(args.n, len(items)))
    dataset = _SubsetDataset(full, n)
    print(f"[setup] {n} consultations × {len(DEFAULT_REGISTRY.models)} models "
          f"= {n * len(DEFAULT_REGISTRY.models)} pipeline runs")

    # scispaCy NER for entity grounding
    try:
        from eval.metrics.grounding import load_scispacy_nlp
        nlp = load_scispacy_nlp()
        print(f"[setup] scispacy NER: {'loaded' if nlp else 'disabled'}")
    except Exception as e:
        print(f"[setup] scispacy NER unavailable ({e})")
        nlp = None

    ctx = PatientContext(patient_ref="Patient/primock57",
                         encounter_ref="Encounter/primock57")
    # Build a throwaway scribe so the harness has a base; run_bakeoff rebuilds
    # a fresh scribe per model via build_scribe_for_model.
    base = _build_scribe(DEFAULT_REGISTRY.models[0].ollama_tag)
    harness = EvalHarness(base, ctx, nlp=nlp)

    host = ModelHost(loader=_loader, evictor=_evictor)

    t0 = time.time()
    bake = harness.run_bakeoff(
        dataset, DEFAULT_REGISTRY,
        build_scribe_for_model=lambda spec: _build_scribe(spec.ollama_tag),
        model_host=host,
    )
    elapsed = time.time() - t0
    print(f"\n[bake-off] done in {elapsed:.0f}s, evictions={host.evictions}")

    # Persist raw metrics as JSON
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = {
        "n_items": n,
        "dataset": full.name,
        "elapsed_seconds": round(elapsed, 1),
        "registry": [
            {"model_id": m.model_id, "ollama_tag": m.ollama_tag,
             "memory_gb": m.memory_gb, "prompt_notes": m.prompt_notes}
            for m in DEFAULT_REGISTRY.models
        ],
        "per_model": {
            mid: {"metrics": sub.metrics}
            for mid, sub in bake.per_model.items()
        },
    }
    json_path = out_dir / "bakeoff_report.json"
    json_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    print(f"[write] {json_path}")

    md = render_bakeoff_report(bake, title="Phase-4 Note-LLM Bake-off")
    md_path = out_dir / "bakeoff_report.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"[write] {md_path}")

    print("\n── summary ──")
    for mid, sub in bake.per_model.items():
        g = sub.metrics.get("grounding", {})
        c = sub.metrics.get("completeness", {})
        print(f"  {mid:16} grounding={g}  completeness={c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
