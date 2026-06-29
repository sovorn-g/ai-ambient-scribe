"""Debug the Phase-2 grounding failure on real PriMock57 audio.

Caches the dialogue to disk so we can iterate on the LLM/citation loop without
re-running ASR + diarization (66s + 32s) every time.

Usage:
    .venv/bin/python scripts/debug_grounded_note.py          # build cache + debug
    .venv/bin/python scripts/debug_grounded_note.py --cache  # reuse cached dialogue
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scribe.dialogue import DialogueExtractor
from scribe.dialogue.diarizer.sherpa_onnx import SherpaOnnxDiarizer
from scribe.dialogue.transcriber.mlx_whisper import MlxWhisperTranscriber
from scribe.domain.types import Dialogue
from scribe.notes import NoteGenerator
from scribe.notes.citations import CitationValidator
from scribe.notes.decode import parse_soap_note
from scribe.notes.llm.ollama import OllamaLLMClient
from scribe.notes.prompt import SOAP_SCHEMA, build_prompt
from eval.datasets.primock57 import PriMock57Dataset

SHERPA_DIR = ROOT / "data" / ".cache" / "sherpa-models"
SEG_MODEL = str(SHERPA_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx")
EMB_MODEL = str(SHERPA_DIR / "nemo_en_titanet_small.onnx")
CACHE = ROOT / "data" / ".cache" / "debug_dialogue.json"


def build_or_load_dialogue(use_cache: bool) -> Dialogue:
    if use_cache and CACHE.exists():
        print(f"[cache] loading {CACHE}")
        return Dialogue.model_validate_json(CACHE.read_text())

    dataset = PriMock57Dataset(data_dir=str(ROOT / "data" / "primock57"))
    item = dataset.items()[0]
    print(f"[asr+diarize] item={item.item_id}")
    t0 = time.time()
    ext = DialogueExtractor(
        MlxWhisperTranscriber(model_id="mlx-community/whisper-large-v3-turbo"),
        SherpaOnnxDiarizer(model_path=EMB_MODEL, segmentation_model_path=SEG_MODEL,
                           num_threads=2, num_clusters=2, threshold=0.5),
    )
    dialogue = ext.extract(item.audio)
    print(f"[asr+diarize] done in {time.time()-t0:.1f}s — {len(dialogue.utterances)} utterances")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(dialogue.model_dump_json(indent=2), encoding="utf-8")
    return dialogue


def main() -> int:
    use_cache = "--cache" in sys.argv
    dialogue = build_or_load_dialogue(use_cache)

    print(f"\n— dialogue summary —")
    roles = {}
    spks = {}
    for u in dialogue.utterances:
        roles[u.role.name] = roles.get(u.role.name, 0) + 1
        spks[u.speaker_id] = spks.get(u.speaker_id, 0) + 1
    print(f"  {len(dialogue.utterances)} utterances")
    print(f"  roles: {roles}")
    print(f"  speakers: {spks}")
    print(f"  first 5 ids: {[u.id for u in dialogue.utterances[:5]]}")
    print(f"  last 5 ids:  {[u.id for u in dialogue.utterances[-5:]]}")

    print(f"\n— first 6 utterances —")
    for u in dialogue.utterances[:6]:
        print(f"  [{u.id}] {u.role.value:9} spk={u.speaker_id}  {u.text[:70]!r}")

    print(f"\n— prompt sent to LLM (first 1500 chars) —")
    prompt = build_prompt(dialogue)
    print(prompt[:1500])
    print(f"  ... (prompt total {len(prompt)} chars)")

    print(f"\n— calling Ollama qwen2.5:7b —")
    llm = OllamaLLMClient(model_id="qwen2.5:7b-instruct-q4_K_M")
    t0 = time.time()
    raw = llm.complete(prompt, SOAP_SCHEMA)
    print(f"  LLM responded in {time.time()-t0:.1f}s, type={type(raw).__name__}")
    raw_str = json.dumps(raw, indent=2) if not isinstance(raw, str) else raw
    debug_out = ROOT / "data" / ".cache" / "debug_llm_raw.txt"
    debug_out.parent.mkdir(parents=True, exist_ok=True)
    debug_out.write_text(raw_str, encoding="utf-8")
    print(f"\n— raw LLM response (first 2500 chars) —")
    print(raw_str[:2500])
    print(f"  ... (full response saved to {debug_out}, {len(raw_str)} chars)")

    print(f"\n— parsed SOAPNote —")
    note = parse_soap_note(raw)
    index = {u.id: u for u in dialogue.utterances}
    print(f"  index has {len(index)} utterance ids: {list(index.keys())[:5]}...")
    for section in ("subjective", "objective", "assessment", "plan"):
        claims = getattr(note, section)
        print(f"\n  {section}: {len(claims)} claims")
        for c in claims[:4]:
            print(f"    text: {c.text[:60]!r}")
            print(f"    citations: {[(r.utterance_id, r.char_span) for r in c.citations]}")
            for r in c.citations:
                exists = r.utterance_id in index
                print(f"      → {r.utterance_id!r} exists_in_index={exists}"
                      + (f"  text={index[r.utterance_id].text[:50]!r}" if exists else ""))

    print(f"\n— validation —")
    validator = CitationValidator()
    result = validator.validate(note, dialogue)
    from scribe.notes.citations import Violations
    if isinstance(result, Violations):
        print(f"  ALL {len(result.items)} claims rejected:")
        for v in result.items[:6]:
            print(f"    [{v.section}] {v.reason}: {v.claim_text[:60]!r}")
    else:
        print(f"  GROUNDED — {sum(len(getattr(result,s)) for s in ('subjective','objective','assessment','plan'))} claims survived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
