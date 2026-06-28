"""ACI-Bench dataset adapter — reference SOAP notes for completeness scoring.

Expects data_dir to contain:
  *.wav           — encounter audio files
  *.note.txt      — reference SOAP note text (stem matches wav)

Returns empty list if data_dir does not exist (keeps tests green without real data).
"""
from __future__ import annotations

from pathlib import Path

from scribe.domain.types import Audio
from eval.datasets.base import Dataset, DatasetItem


class ACIBenchDataset(Dataset):
    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)

    @property
    def name(self) -> str:
        return "acibench"

    def items(self) -> list[DatasetItem]:
        if not self._dir.exists():
            return []

        result = []
        for wav_path in sorted(self._dir.glob("*.wav")):
            item_id = wav_path.stem

            ref_note: str | None = None
            note_path = self._dir / f"{item_id}.note.txt"
            if note_path.exists():
                ref_note = note_path.read_text(encoding="utf-8").strip()

            result.append(DatasetItem(
                item_id=item_id,
                audio=Audio(source="file", path=str(wav_path)),
                reference_note=ref_note,
            ))
        return result
