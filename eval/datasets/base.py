"""Dataset seam — two adapters (PriMock57, ACI-Bench) → real seam (design.md §5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from scribe.domain.types import Audio


@dataclass
class DatasetItem:
    item_id: str
    audio: Audio
    reference_transcript: str | None = None  # for WER
    reference_rttm: str | None = None         # RTTM text for DER
    reference_note: str | None = None         # reference SOAP text for completeness


class Dataset(ABC):
    """Abstract dataset — two adapters make this seam real."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def items(self) -> list[DatasetItem]: ...
