"""Live audio buffer — accumulates PCM16 chunks, writes WAV files.

Phase 7 ambient listening. Pure, deterministic, no seam — just byte handling.
The ``AmbientSessionService`` (scribe/app/ambient.py) owns one of these per
session and uses it both for preview-window extraction and final-batch WAV
writing.

Conventions:
  * Chunks are raw PCM16 little-endian mono (``int16`` samples, 2 bytes each).
  * Sample rate is fixed per session (16 kHz from the browser; backend does no
    resampling — the frontend is responsible for delivering 16 kHz).
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path


class LiveAudioBuffer:
    """Append-only PCM16 buffer with WAV-file emission."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self._bytes = bytearray()

    def append(self, pcm16: bytes) -> None:
        """Append a PCM16 little-endian chunk. Length must be even (whole samples)."""
        if len(pcm16) % 2 != 0:
            # Drop the trailing odd byte rather than corrupt frame alignment.
            pcm16 = pcm16[:-1]
        self._bytes.extend(pcm16)

    @property
    def byte_count(self) -> int:
        return len(self._bytes)

    @property
    def sample_count(self) -> int:
        return len(self._bytes) // 2

    def duration_seconds(self) -> float:
        return self.sample_count / self.sample_rate if self.sample_rate else 0.0

    def extract_window(self, start_seconds: float, end_seconds: int | float) -> bytes:
        """Return PCM16 bytes for [start_seconds, end_seconds) of the buffer.

        Clamped to the available buffer. Returns b"" if the window is empty.
        """
        start_sample = int(start_seconds * self.sample_rate)
        end_sample = int(float(end_seconds) * self.sample_rate)
        start_sample = max(0, start_sample)
        end_sample = max(start_sample, end_sample)
        start_byte = start_sample * 2
        end_byte = end_sample * 2
        return bytes(self._bytes[start_byte:end_byte])

    def write_wav(self, path: str | Path | None = None) -> str:
        """Write the full buffer as a mono WAV file. Returns the file path.

        If ``path`` is None, writes to a temp file (delete=False — caller owns
        cleanup via the OS temp dir; the pipeline reads it once).
        """
        target = str(path) if path is not None else tempfile.NamedTemporaryFile(
            delete=False, suffix=".wav"
        ).name
        _write_wav(target, bytes(self._bytes), self.sample_rate, self.channels)
        return target

    def write_window_wav(self, start_seconds: float, end_seconds: float) -> str:
        """Write a [start, end) window as a temp WAV. Returns the path."""
        pcm = self.extract_window(start_seconds, end_seconds)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        _write_wav(tmp.name, pcm, self.sample_rate, self.channels)
        return tmp.name


def _write_wav(path: str, pcm16: bytes, sample_rate: int, channels: int) -> None:
    """Write a canonical 44-byte-header WAV (PCM16) to ``path``."""
    num_samples = len(pcm16) // 2
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,             # PCM chunk size
        1,              # audio format = PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,             # bits per sample
        b"data",
        data_size,
    )
    with open(path, "wb") as f:
        f.write(header)
        f.write(pcm16)
