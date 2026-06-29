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
        segmentation_model_path: str | None = None,
        num_threads: int = 1,
        num_clusters: int = -1,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        min_duration_on: float = 0.3,
        min_duration_off: float = 0.5,
    ) -> None:
        if not model_path:
            raise ValueError("SherpaOnnxDiarizer requires a model_path")
        self.model_path = model_path
        self.segmentation_model_path = segmentation_model_path
        self.num_threads = num_threads
        self.num_clusters = num_clusters
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.min_duration_on = min_duration_on
        self.min_duration_off = min_duration_off

    @property
    def identifier(self) -> str:
        seg = self.segmentation_model_path or "<default>"
        return f"sherpa-onnx:{self.model_path}|seg={seg}"

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

        if self.segmentation_model_path is None:
            raise ValueError(
                "SherpaOnnxDiarizer requires segmentation_model_path "
                "(a pyannote segmentation .onnx) to run diarization"
            )

        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=self.segmentation_model_path,
                ),
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=self.model_path,
                num_threads=self.num_threads,
                debug=False,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=self.num_clusters,
                threshold=self.threshold,
            ),
            min_duration_on=self.min_duration_on,
            min_duration_off=self.min_duration_off,
        )
        if not config.validate():
            raise RuntimeError(
                "sherpa-onnx diarization config invalid — "
                "need both segmentation_model_path and model_path pointing at real files"
            )
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        result = diarizer.process(samples)
        raw_segments = result.sort_by_start_time()
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
    """Return mono float32 PCM samples at ``sample_rate`` for sherpa-onnx.

    sherpa-onnx's ``OfflineSpeakerDiarization.process`` accepts a 1-D float32
    numpy array in the range [-1, 1] at the configured sample rate (16k).
    """
    if audio.samples is not None:
        return audio.samples

    # Read wav via stdlib + numpy. sherpa-onnx >= 1.10 dropped its bundled
    # ``read_wave`` helper, so we do it ourselves — keeps the adapter free of
    # soundfile/librosa deps (numpy is already transitive via spacy/jiwer).
    import wave
    import numpy as np

    with wave.open(str(audio.path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sr != sample_rate:
        # sherpa-onnx expects 16k; defer resampling to the caller for now.
        # (A real resampler lands when the mic/stream adapter does in Phase 5.)
        raise ValueError(
            f"Audio sample rate {sr} does not match diarizer expected {sample_rate}. "
            "Resample to 16k before diarizing."
        )

    # Decode PCM → float32 mono in [-1, 1].
    if sampwidth == 2:
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported wav sample width: {sampwidth} bytes")

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data
