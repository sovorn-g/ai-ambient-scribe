/**
 * liveAudio.ts — browser mic capture + PCM16 chunk encoding (Phase 7).
 *
 * Captures the default mic via getUserMedia, resamples to 16 kHz mono, encodes
 * to little-endian PCM16, and emits chunks on a schedule.
 *
 * No cloud, no Web Speech API. Pure local PCM.
 */

export interface LevelSample {
  rms: number; // 0..1 rough loudness for the UI meter
  peak: number; // 0..1
}

export type ChunkHandler = (pcm16: ArrayBuffer) => void;
export type LevelHandler = (level: LevelSample) => void;

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_MS = 500; // 500ms chunks → 2 chunks/sec over the WebSocket

/**
 * LiveMicRecorder — owns a MediaStream + AudioContext, emits PCM16 chunks.
 *
 * Use:
 *   const rec = new LiveMicRecorder();
 *   await rec.start({ onChunk, onLevel });
 *   ...
 *   await rec.stop();
 */
export class LiveMicRecorder {
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private scriptNode: ScriptProcessorNode | null = null;
  private analyser: AnalyserNode | null = null;
  private freqData: Uint8Array<ArrayBuffer> | null = null;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private ring: Float32Array[] = [];
  private onChunk: ChunkHandler | null = null;
  private onLevel: LevelHandler | null = null;

  async start(handlers: { onChunk: ChunkHandler; onLevel?: LevelHandler }): Promise<void> {
    if (this.stream) throw new Error("already recording");
    this.onChunk = handlers.onChunk;
    this.onLevel = handlers.onLevel ?? null;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    this.audioCtx = new AudioContext();
    this.sourceNode = this.audioCtx.createMediaStreamSource(this.stream);

    // AnalyserNode taps the raw mic signal for FFT frequency bins — drives the
    // voice-reactive equalizer bars at 60fps via getFrequencyBins(). It's a
    // passive tap off the source; it does not need to connect onward.
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;       // 128 bins
    this.analyser.smoothingTimeConstant = 0.78; // smooth bar motion between frames
    this.freqData = new Uint8Array(this.analyser.frequencyBinCount);
    this.sourceNode.connect(this.analyser);

    // The audio graph is PULLED from the destination. Any node that isn't
    // connected (directly or transitively) to the destination will never have
    // its process() / onaudioprocess fired in Chrome. So both paths connect
    // through a zero-gain mute node to the destination — no speaker output, but
    // the graph actually pulls samples through.
    const mute = this.audioCtx.createGain();
    mute.gain.value = 0;
    mute.connect(this.audioCtx.destination);

    // Try AudioWorklet first; fall back to ScriptProcessorNode (deprecated but
    // universally supported) if the worklet module can't load.
    let usedWorklet = false;
    try {
      const workletUrl = makePcmWorkletUrl();
      await this.audioCtx.audioWorklet.addModule(workletUrl);
      // numberOfOutputs: 1 so we can connect it into the graph (the worklet
      // emits silence on its output; the real data goes via port.postMessage).
      this.workletNode = new AudioWorkletNode(this.audioCtx, "pcm-collector", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        channelCount: 1,
        outputChannelCount: [1],
      });
      this.sourceNode.connect(this.workletNode);
      this.workletNode.connect(mute);
      let workletFrameCount = 0;
      this.workletNode.port.onmessage = (e) => {
        if (e.data.samples && e.data.samples.length) {
          this.ring.push(e.data.samples);
          this.ingestLevel(e.data.samples);
          workletFrameCount += e.data.samples.length;
        }
      };
      usedWorklet = true;
      console.info("[ambient] AudioWorklet path active (sr=%d)", this.audioCtx.sampleRate);
      // Sanity probe: if no samples arrive within 1.5s, the worklet isn't being
      // pulled — log it so the bug is obvious in the console.
      setTimeout(() => {
        if (workletFrameCount === 0) {
          console.warn("[ambient] worklet posted 0 frames in 1.5s — graph not pulling? Falling back not triggered.");
        }
      }, 1500);
    } catch (err) {
      console.warn("[ambient] worklet load failed, falling back to ScriptProcessor:", err);
      usedWorklet = false;
    }

    if (!usedWorklet) {
      // ScriptProcessorNode fallback. Buffer size 4096 frames.
      const sp = this.audioCtx.createScriptProcessor(4096, 1, 1);
      sp.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        this.ring.push(new Float32Array(input));
        this.ingestLevel(input);
      };
      this.sourceNode.connect(sp);
      sp.connect(mute);
      this.scriptNode = sp;
      console.info("[ambient] ScriptProcessor path active (sr=%d)", this.audioCtx.sampleRate);
    }

    // Flush a PCM16 chunk on a fixed cadence from whatever has accumulated.
    this.intervalId = setInterval(() => this.flushChunk(), CHUNK_MS);
  }

  private flushChunk(): void {
    if (this.ring.length === 0) {
      return;
    }
    const combined = concatFloat32(this.ring);
    this.ring = [];
    if (combined.length === 0) return;
    const resampled = resampleTo16k(combined, this.audioCtx?.sampleRate ?? 48000);
    const pcm16 = float32ToPcm16Le(resampled);
    this.onChunk?.(pcm16);
    // Throttled log: every ~2s (every 4th chunk at 500ms cadence).
    this._chunkCount = (this._chunkCount ?? 0) + 1;
    if (this._chunkCount % 4 === 1) {
      const rms = (() => {
        let s = 0;
        for (let i = 0; i < resampled.length; i++) s += resampled[i] * resampled[i];
        return Math.sqrt(s / (resampled.length || 1));
      })();
      console.debug(
        "[ambient] chunk #%d bytes=%d samples=%d sr16k rms=%f",
        this._chunkCount, pcm16.byteLength, resampled.length, rms.toFixed(4),
      );
    }
  }

  private _chunkCount?: number;

  private ingestLevel(samples: Float32Array): void {
    if (!this.onLevel) return;
    let sum = 0;
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      const v = Math.abs(samples[i]);
      sum += samples[i] * samples[i];
      if (v > peak) peak = v;
    }
    const rms = Math.sqrt(sum / (samples.length || 1));
    this.onLevel({ rms, peak });
    // Throttled: log the first non-trivial level, then ~1/s.
    this._levelLogAt ??= 0;
    if ((rms > 0.01 || peak > 0.05) && Date.now() - this._levelLogAt > 1000) {
      this._levelLogAt = Date.now();
      console.debug("[ambient] level rms=%f peak=%f", rms.toFixed(4), peak.toFixed(4));
    }
  }

  private _levelLogAt?: number;

  /**
   * Read FFT frequency bins from the AnalyserNode and downsample to `n` bars.
   * Returns `n` values in 0..1, low→high frequency. Returns zeros if not
   * recording or the analyser isn't ready. Call this from a requestAnimationFrame
   * loop for 60fps visualisation — do NOT put it in React state.
   */
  getFrequencyBins(n: number): Float32Array {
    const out = new Float32Array(n);
    if (!this.analyser || !this.freqData) return out;
    this.analyser.getByteFrequencyData(this.freqData);
    const binCount = this.freqData.length; // 128 for fftSize=256
    // Use the lower ~80% of bins (upper bins are usually empty for speech).
    const usable = Math.max(1, Math.floor(binCount * 0.8));
    const per = usable / n;
    for (let i = 0; i < n; i++) {
      const start = Math.floor(i * per);
      const end = Math.min(binCount, Math.floor((i + 1) * per));
      let max = 0;
      for (let j = start; j < end; j++) {
        if (this.freqData[j] > max) max = this.freqData[j];
      }
      // 0..255 → 0..1 with a gentle gamma so quiet speech still shows motion.
      out[i] = Math.pow(max / 255, 0.7);
    }
    return out;
  }

  async stop(): Promise<void> {
    if (this.intervalId) clearInterval(this.intervalId);
    this.intervalId = null;
    // Flush any remaining audio.
    this.flushChunk();
    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    this.freqData = null;
    if (this.audioCtx) {
      await this.audioCtx.close();
      this.audioCtx = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    this.onChunk = null;
    this.onLevel = null;
    this.ring = [];
  }
}

// ── DSP helpers ───────────────────────────────────────────────────────────────

function concatFloat32(arrs: Float32Array[]): Float32Array {
  let total = 0;
  for (const a of arrs) total += a.length;
  const out = new Float32Array(total);
  let off = 0;
  for (const a of arrs) {
    out.set(a, off);
    off += a.length;
  }
  return out;
}

function resampleTo16k(input: Float32Array, srcRate: number): Float32Array {
  if (srcRate === TARGET_SAMPLE_RATE) return input;
  const ratio = srcRate / TARGET_SAMPLE_RATE;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const srcIdx = i * ratio;
    const lo = Math.floor(srcIdx);
    const hi = Math.min(lo + 1, input.length - 1);
    const frac = srcIdx - lo;
    out[i] = input[lo] * (1 - frac) + input[hi] * frac;
  }
  return out;
}

function float32ToPcm16Le(input: Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(input.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < input.length; i++) {
    let s = Math.max(-1, Math.min(1, input[i]));
    s = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(i * 2, s, true);
  }
  return buf;
}

function makePcmWorkletUrl(): string {
  // NOTE: inside AudioWorkletProcessor, `port` is a property of the instance
  // (this.port), NOT a global. Using `port` directly throws ReferenceError and
  // kills process() on the first block — no samples ever flow.
  const code = `
class PcmCollector extends AudioWorkletProcessor {
  constructor() {
    super();
  }
  process(inputs, outputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) {
      this.port.postMessage({ samples: new Float32Array(ch) });
    }
    // Output is intentionally silence — we only need the node connected to
    // destination so the graph pulls process() on each block.
    return true;
  }
}
registerProcessor('pcm-collector', PcmCollector);
`;
  return URL.createObjectURL(new Blob([code], { type: "application/javascript" }));
}
