"""PriMock57 dataset adapter.

Expects data_dir to contain:
  *.wav            — audio files (mixed mono 16k, see scripts/fetch_primock57.py)
  *.txt            — reference transcripts (optional; stem matches wav)
  *.rttm           — reference diarization in RTTM format (optional; stem matches wav)
  *.note.json      — reference clinician note JSON (optional; stem matches wav)

Returns empty list if data_dir does not exist (keeps tests green without real data).
"""
from __future__ import annotations

import json
from pathlib import Path

from scribe.domain.types import Audio
from eval.datasets.base import Dataset, DatasetItem


class PriMock57Dataset(Dataset):
    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)

    @property
    def name(self) -> str:
        return "primock57"

    def items(self) -> list[DatasetItem]:
        if not self._dir.exists():
            return []

        result = []
        for wav_path in sorted(self._dir.glob("*.wav")):
            item_id = wav_path.stem

            ref_transcript: str | None = None
            txt = wav_path.with_suffix(".txt")
            if txt.exists():
                ref_transcript = txt.read_text(encoding="utf-8").strip()

            ref_rttm: str | None = None
            rttm = wav_path.with_suffix(".rttm")
            if rttm.exists():
                ref_rttm = rttm.read_text(encoding="utf-8").strip()

            ref_note: str | None = None
            note_json = wav_path.with_suffix(".note.json")
            if note_json.exists():
                try:
                    payload = json.loads(note_json.read_text(encoding="utf-8"))
                    # Upstream PriMock57 ships the SOAP note under the "note" key.
                    ref_note = (payload.get("note") or "").strip() or None
                except (json.JSONDecodeError, OSError):
                    ref_note = None

            result.append(DatasetItem(
                item_id=item_id,
                audio=Audio(source="file", path=str(wav_path)),
                reference_transcript=ref_transcript,
                reference_rttm=ref_rttm,
                reference_note=ref_note,
            ))
        return result
