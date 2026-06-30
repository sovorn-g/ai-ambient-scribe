"use client";

import { useEffect, useRef, useState } from "react";
import { LiveMicRecorder } from "@/lib/liveAudio";
import { openAmbientSocket, type AmbientEvent } from "@/lib/api";
import type { DraftResponse } from "@/lib/types";

interface Props {
  patientRef: string;
  encounterRef: string;
  /** Called when the final batch draft is ready (same shape as upload path). */
  onDraftReady: (draft: DraftResponse) => void;
  /** Called when an error occurs that should surface to the page. */
  onError: (msg: string) => void;
}

type RecState = "idle" | "requesting" | "listening" | "finalizing";

const N_BARS = 28;

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function AmbientRecorder({
  patientRef,
  encounterRef,
  onDraftReady,
  onError,
}: Props) {
  const [state, setState] = useState<RecState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const recorderRef = useRef<LiveMicRecorder | null>(null);
  const sockRef = useRef<ReturnType<typeof openAmbientSocket> | null>(null);
  const startRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Imperative visual refs — driven by a requestAnimationFrame loop reading
  // the AnalyserNode FFT bins at 60fps. Bypassing React state avoids re-render
  // storms and gives smooth bar motion.
  const barRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const ringRef = useRef<HTMLSpanElement | null>(null);
  const peakRef = useRef<HTMLSpanElement | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      // cleanup on unmount
      void recorderRef.current?.stop();
      sockRef.current?.close();
      if (timerRef.current) clearInterval(timerRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // 60fps visual loop — reads FFT bins from the recorder's AnalyserNode and
  // sets bar heights + ring scale imperatively. Runs only while listening.
  useEffect(() => {
    if (state !== "listening") {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }
    let alive = true;
    const tick = () => {
      if (!alive) return;
      const rec = recorderRef.current;
      if (rec) {
        const bins = rec.getFrequencyBins(N_BARS);
        let sum = 0;
        let maxBin = 0;
        for (let i = 0; i < N_BARS; i++) {
          const v = bins[i];
          sum += v;
          if (v > maxBin) maxBin = v;
          const el = barRefs.current[i];
          if (el) el.style.height = `${Math.max(4, v * 60)}px`;
        }
        const avg = sum / N_BARS;
        if (ringRef.current) {
          ringRef.current.style.transform = `scale(${1 + Math.min(1, avg * 1.6) * 0.18})`;
        }
        if (peakRef.current) {
          peakRef.current.style.opacity = maxBin > 0.05 ? `${0.4 + Math.min(1, maxBin) * 0.6}` : "0";
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      alive = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [state]);

  function handleEvent(e: AmbientEvent) {
    switch (e.type) {
      case "session_started":
        setStatusMsg("Listening…");
        break;
      case "listening":
        if (startRef.current) setElapsed((Date.now() - startRef.current) / 1000);
        break;
      case "finalizing":
        setState("finalizing");
        setStatusMsg("Generating final note…");
        break;
      case "draft_ready":
        onDraftReady(e.draft);
        break;
      case "cancelled":
        reset();
        break;
      case "error":
        onError(e.message);
        reset();
        break;
    }
  }

  async function startListening() {
    setState("requesting");
    setStatusMsg("Requesting microphone…");
    setElapsed(0);
    console.info("[ambient] startListening: patient=%s encounter=%s", patientRef, encounterRef);
    try {
      const sock = openAmbientSocket({ onEvent: handleEvent });
      sockRef.current = sock;
      const rec = new LiveMicRecorder();
      recorderRef.current = rec;
      await rec.start({
        onChunk: (pcm16) => sock.sendAudio(pcm16),
        // No-op level handler keeps the throttled RMS/peak log alive inside
        // the recorder (it early-returns when onLevel is unset). Visuals are
        // driven by the AnalyserNode rAF loop, not by this callback.
        onLevel: () => {},
      });
      console.info("[ambient] recorder started; sending start command");
      sock.start(patientRef, encounterRef);
      setState("listening");
      startRef.current = Date.now();
      timerRef.current = setInterval(() => {
        if (startRef.current) setElapsed((Date.now() - startRef.current) / 1000);
      }, 250);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("[ambient] startListening failed:", e);
      onError(/permission|denied|notallowed/i.test(msg) ? "Microphone permission denied." : msg);
      reset();
    }
  }

  async function endConsultation() {
    if (timerRef.current) clearInterval(timerRef.current);
    // IMPORTANT: stop the recorder FIRST so its final flush lands on the
    // socket BEFORE we send `stop`. The backend finalizes on whatever audio
    // it has received at the moment `stop` is processed — a late chunk
    // arriving after `stop` is dropped (and could even error).
    console.info("[ambient] endConsultation: stopping recorder (flush final chunk)…");
    try {
      await recorderRef.current?.stop();
    } catch (e) {
      console.error("[ambient] recorder.stop() failed", e);
    }
    recorderRef.current = null;
    console.info("[ambient] endConsultation: sending stop…");
    sockRef.current?.stop();
  }

  function cancelListening() {
    sockRef.current?.cancel();
    reset();
  }

  function reset() {
    if (timerRef.current) clearInterval(timerRef.current);
    void recorderRef.current?.stop();
    recorderRef.current = null;
    sockRef.current?.close();
    sockRef.current = null;
    setState("idle");
    setElapsed(0);
    setStatusMsg(null);
    startRef.current = null;
  }

  return (
    <div className="card px-7 py-8 flex flex-col items-center gap-5">
      <div className="flex items-center gap-2 self-start">
        <p className="label-caps">Live Listening</p>
        <span className="label-caps text-dusty/50">· ambient mic capture</span>
      </div>

      <p className="font-lora text-sm text-dusty/80 leading-snug text-center">
        Click the circle, talk, then stop.
      </p>

      {/* ── Round listening dial ──────────────────────────────────────────── */}
      <div
        className="relative flex items-center justify-center select-none"
        style={{ width: 260, height: 260 }}
      >
        {/* outer pulse rings (only while listening) */}
        {state === "listening" && (
          <>
            <span
              className="absolute rounded-full border-2 border-clinical/30 motion-reduce:animate-none"
              style={{
                width: 260,
                height: 260,
                animation: "ambient-pulse 2.4s ease-out infinite",
              }}
            />
            <span
              className="absolute rounded-full border border-clinical/20 motion-reduce:animate-none"
              style={{
                width: 260,
                height: 260,
                animation: "ambient-pulse 2.4s ease-out infinite 0.8s",
              }}
            />
          </>
        )}

        {/* live red ring while recording — scale driven by rAF loop via ref */}
        {state === "listening" && (
          <span
            ref={ringRef}
            className="absolute rounded-full border-2 border-red-500/80"
            style={{
              width: 220,
              height: 220,
              transform: "scale(1)",
              transition: "transform 80ms linear",
            }}
          />
        )}

        {/* core circle */}
        <div
          className={`relative rounded-full flex flex-col items-center justify-center transition-colors ${
            state === "listening"
              ? "bg-clinical text-white"
              : state === "finalizing"
              ? "bg-clinical/70 text-white"
              : state === "requesting"
              ? "bg-ruled/30 text-nuit"
              : "bg-vellum border-2 border-clinical/40 text-clinical hover:bg-clinical/5"
          }`}
          style={{ width: 200, height: 200 }}
        >
          {/* waveform bars — heights driven by rAF loop reading FFT bins */}
          {state === "listening" && (
            <div className="flex items-center justify-center gap-[3px] h-16 px-4">
              {Array.from({ length: N_BARS }, (_, i) => (
                <span
                  key={i}
                  ref={(el) => { barRefs.current[i] = el; }}
                  className="w-[4px] rounded-full bg-white/90"
                  style={{
                    height: "6px",
                    opacity: 0.9,
                  }}
                />
              ))}
            </div>
          )}

          {/* finalizing: spinning ring inside the circle (not frozen bars) */}
          {state === "finalizing" && (
            <div className="flex flex-col items-center gap-3">
              <div
                className="w-12 h-12 rounded-full border-[3px] border-white/25 border-t-white motion-reduce:animate-none"
                style={{ animation: "ambient-spin 0.9s linear infinite" }}
              />
              <span className="label-caps text-white/90">Processing</span>
            </div>
          )}

          {/* idle / requesting: icon */}
          {state === "idle" && (
            <div className="flex flex-col items-center gap-2">
              <span className="font-black text-3xl leading-none">●</span>
              <span className="label-caps">Record</span>
            </div>
          )}
          {state === "requesting" && (
            <div className="flex flex-col items-center gap-2">
              <div className="w-7 h-7 border-2 border-nuit/40 border-t-clinical rounded-full animate-spin motion-reduce:animate-none" />
              <span className="label-caps">Requesting mic…</span>
            </div>
          )}

          {/* timer overlay */}
          {state === "listening" && (
            <div className="mt-3 font-mono text-sm tabular-nums tracking-widest">
              {fmtTime(elapsed)}
            </div>
          )}
        </div>

        {/* peak indicator dot — opacity driven by rAF loop via ref */}
        {state === "listening" && (
          <span
            ref={peakRef}
            className="absolute rounded-full bg-red-500"
            style={{ width: 8, height: 8, top: 18, right: 18, opacity: 0 }}
            aria-hidden="true"
          />
        )}
      </div>

      {/* status line */}
      {statusMsg && state !== "idle" && (
        <p className="font-grotesk text-xs text-dusty/80 -mt-1">{statusMsg}</p>
      )}

      {/* ── Controls ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 min-h-[44px]">
        {state === "idle" && (
          <button
            type="button"
            onClick={startListening}
            className="label-caps bg-clinical text-white px-6 py-2.5 rounded-full hover:bg-clinical/90 active:scale-[0.98] transition-[background-color,transform] shadow-sm"
          >
            ● Record
          </button>
        )}
        {state === "listening" && (
          <>
            <button
              type="button"
              onClick={endConsultation}
              className="label-caps bg-nuit text-vellum px-6 py-2.5 rounded-full hover:bg-nuit/90 active:scale-[0.98] transition-[background-color,transform] shadow-sm"
            >
              ■ Stop &amp; generate
            </button>
            <button
              type="button"
              onClick={cancelListening}
              className="label-caps text-dusty hover:text-alert transition-colors px-2"
            >
              cancel
            </button>
          </>
        )}
        {state === "finalizing" && (
          <div className="flex items-center gap-2 text-dusty/70">
            <div
              className="w-4 h-4 rounded-full border-2 border-ruled border-t-clinical motion-reduce:animate-none"
              style={{ animation: "ambient-spin 0.9s linear infinite" }}
            />
            <span className="label-caps">running batch pipeline…</span>
          </div>
        )}
      </div>

      {/* keyframes for the pulse rings + finalizing spinner */}
      <style>{`
        @keyframes ambient-pulse {
          0%   { transform: scale(1);    opacity: 0.6; }
          70%  { transform: scale(1.25); opacity: 0;   }
          100% { transform: scale(1.25); opacity: 0;   }
        }
        @keyframes ambient-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
