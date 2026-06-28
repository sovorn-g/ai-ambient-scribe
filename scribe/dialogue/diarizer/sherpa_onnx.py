"""SherpaOnnxDiarizer — real Diarizer adapter backed by sherpa-onnx.

sherpa-onnx is provably offline, Apache-2.0, no HF token — matches the
privacy constraint (design.md §3, execute-plan-v2.md §3). The heavy import
(``sherpa_onnx``) is deferred to ``__init__`` so importing this module never
requires the optional dep; CI tests the *adapter shape* via the pure
``segments_to_turns`` mapping plus import-guarded ``diarize`` behaviour.

HYPOTHETICAL seam (design.md §5): one adapter. No swappability theatre.
"""

from __future__ import annotations

from typing import Any

from scribe.domain.types import Audio, SpeakerTurn, TimeSpan
from scribe.dialogue.diarizer.base import Diarizer


class SherpaOnnxDiarizer(Diarizer):
    """Wrap sherpa-onnx ``OfflineSpeakerDiarization`` → ``[SpeakerTurn]``."""

    def __init__(
        self,
        *,
        model_path: str,
        num_threads: int = 1,
        num_clusters: int = -1,
        threshold: float = 0.5,
        sample_rate: int = 16000,
    ) -> None:
        if not model_path:
            raise ValueError("SherpaOnnxDiarizer requires a model_path")
        self.model_path = model_path
        self.num_threads = num_threads
        self.num_clusters = num_clusters
        self.threshold = threshold
        self.sample_rate = sample_rate

    @property
    def identifier(self) -> str:
        return f"sherpa-onnx:{self.model_path}"

    def diarize(self, audio: Audio) -> list[SpeakerTurn]:
        if audio.path is None and audio.samples is None:
            raise ValueError(
                "SherpaOnnxDiarizer requires audio.path or audio.samples"
            )

        try:
            import sherpa_onnx  # type: ignore
        except ImportError as e:  # pragma: no cover - needs sherpa-onnx installed
            raise RuntimeError(
                "sherpa-onnx is not installed. Install with: pip install -e .[phase1]"
            ) from e

        samples = _load_samples(audio, sherpa_onnx, self.sample_rate)

        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=self.model_path,
                num_threads=self.num_threads,
                debug=False,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=self.num_clusters,
                threshold=self.threshold,
            ),
        )
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        raw_segments = diarizer.process(samples)
        return segments_to_turns(raw_segments)


# ── pure mapping — testable without sherpa-onnx ──────────────────────────────
def segments_to_turns(raw_segments: Any) -> list[SpeakerTurn]:
    """Convert sherpa-onnx raw diarization segments to ``[SpeakerTurn]``.

    Each raw segment is expected to expose ``.start``, ``.end``, ``.speaker``
    (the public ``OfflineSpeakerDiarizationSegment`` shape). Speaker ids are
    normalised to ``spk:<int>`` so the rest of the pipeline never sees the
    raw integer.
    """
    turns: list[SpeakerTurn] = []
    for seg in raw_segments:
        start = float(seg.start)
        end = float(seg.end)
        speaker = int(seg.speaker)
        turns.append(
            SpeakerTurn(speaker_id=f"spk:{speaker}", time_span=TimeSpan(start=start, end=end))
        )
    return turns


def _load_samples(audio: Audio, sherpa_onnx: Any, sample_rate: int) -> Any:
    """Return mono PCM samples at ``sample_rate`` for sherpa-onnx."""
    if audio.samples is not None:
        return audio.samples
    # sherpa_onnx.read_wave returns (samples, sample_rate) for a wav path.
    samples, sr = sherpa_onnx.read_wave(str(audio.path))
    if sr != sample_rate:
        # sherpa-onnx expects 16k; defer resampling to the caller for now.
        # (A real resampler lands when the mic/stream adapter does in Phase 5.)
        raise ValueError(
            f"Audio sample rate {sr} does not match diarizer expected {sample_rate}. "
            "Resample to 16k before diarizing."
        )
    return samples
