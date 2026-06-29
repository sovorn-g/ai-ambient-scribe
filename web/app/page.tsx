"use client";

import { useState, useEffect } from "react";
import DraftBanner from "@/components/DraftBanner";
import TranscriptPane from "@/components/TranscriptPane";
import SOAPEditor from "@/components/SOAPEditor";
import AudioUploader from "@/components/AudioUploader";
import ApproveSection from "@/components/ApproveSection";
import { uploadAudio, generateDraft, editDraft, approveDraft, checkHealth } from "@/lib/api";
import type { DraftResponse, DocumentRefResponse, SOAPNote } from "@/lib/types";

type Step = "idle" | "uploading" | "generating" | "review" | "approving" | "done" | "error";

// ── Logo mark ─────────────────────────────────────────────────────────────────
// Rounded-square card with an EKG waveform — audio → clinical record

function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={className}
    >
      <rect width="28" height="28" rx="6" fill="#1B4D82" />
      <path
        d="M4 14h4l2-6 4 12 2.5-8 2 4H24"
        stroke="white"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Step indicator ────────────────────────────────────────────────────────────

const STEPS = [
  { n: "01", label: "Upload"  },
  { n: "02", label: "Review"  },
  { n: "03", label: "Export"  },
];

function stepIdx(step: Step): number {
  if (["idle", "uploading", "generating", "error"].includes(step)) return 0;
  if (["review", "approving"].includes(step)) return 1;
  return 2;
}

function StepBar({ step }: { step: Step }) {
  const cur = stepIdx(step);
  return (
    <div className="flex items-center gap-0" aria-label="Progress">
      {STEPS.map(({ n, label }, i) => (
        <div key={n} className="flex items-center">
          <div className="flex items-baseline gap-1.5">
            <span
              className={`font-grotesk font-black text-sm tabular-nums transition-colors ${
                i < cur ? "text-emerald-600" : i === cur ? "text-clinical" : "text-ruled"
              }`}
            >
              {i < cur ? "✓" : n}
            </span>
            <span
              className={`font-grotesk text-xs tracking-wide transition-colors ${
                i === cur ? "text-nuit font-semibold" : "text-dusty/60"
              }`}
            >
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`mx-4 h-px w-10 transition-colors ${i < cur ? "bg-emerald-400" : "bg-ruled"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Loading card ──────────────────────────────────────────────────────────────

function SpinnerCard({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="card px-8 py-16 flex flex-col items-center gap-4 text-center">
      <div className="w-8 h-8 border-2 border-ruled border-t-clinical rounded-full animate-spin motion-reduce:animate-none" />
      <div>
        <p className="font-grotesk font-semibold text-nuit">{title}</p>
        {sub && <p className="font-grotesk text-sm text-dusty mt-1">{sub}</p>}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const [patientRef,   setPatientRef]   = useState("patient-001");
  const [encounterRef, setEncounterRef] = useState("encounter-001");
  const [step,         setStep]         = useState<Step>("idle");
  const [apiStatus, setApiStatus]       = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    checkHealth().then((h) => setApiStatus(h?.ok ? "ok" : "down"));
  }, []);
  const [draft,        setDraft]        = useState<DraftResponse | null>(null);
  const [editedNote,   setEditedNote]   = useState<SOAPNote | null>(null);
  const [docRef,       setDocRef]       = useState<DocumentRefResponse | null>(null);
  const [error,        setError]        = useState<string | null>(null);

  function friendlyError(e: unknown): string {
    const msg = e instanceof Error ? e.message : String(e);
    if (/networkerror|failed to fetch|load failed/i.test(msg)) {
      return "Cannot reach the API server at localhost:8000. Start it with: uvicorn scribe.api.app:app --reload";
    }
    return msg;
  }

  async function handleUploadAndGenerate(file: File) {
    setError(null);
    setStep("uploading");
    try {
      const { path } = await uploadAudio(file);
      setStep("generating");
      const d = await generateDraft(patientRef, encounterRef, path);
      setDraft(d);
      setEditedNote(d.note);
      setStep("review");
    } catch (e) {
      setError(friendlyError(e));
      setStep("error");
    }
  }

  async function handleApprove(approverName: string) {
    if (!draft || !editedNote) return;
    setStep("approving");
    try {
      await editDraft(draft.id, editedNote);
      const doc = await approveDraft(draft.id, approverName);
      setDocRef(doc);
      setStep("done");
    } catch (e) {
      setError(friendlyError(e));
      setStep("error");
    }
  }

  function reset() {
    setStep("idle");
    setDraft(null);
    setEditedNote(null);
    setDocRef(null);
    setError(null);
  }

  return (
    <div className="min-h-screen bg-vellum">

      {/* Masthead nav */}
      <header className="bg-nuit border-b border-white/10 px-8 py-3.5">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LogoMark size={28} />
            <div className="flex items-baseline gap-2">
              <span className="font-grotesk font-black text-white text-base tracking-[0.12em] uppercase">
                Ambient Scribe
              </span>
              <span className="font-grotesk text-white/30 text-xs">·</span>
              <span className="font-grotesk text-white/40 text-xs tracking-wide">clinical AI</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-[10px] text-white/40 tracking-widest uppercase">
              Local · M4 · FHIR R5
            </span>
            <div
              className="flex items-center gap-1.5"
              title={
                apiStatus === "checking" ? "Checking API…"
                : apiStatus === "ok" ? "API running at localhost:8000"
                : "API unreachable — run: uvicorn scribe.api.app:app --reload"
              }
            >
              <span className={`w-2 h-2 rounded-full ${
                apiStatus === "checking" ? "bg-white/30 animate-pulse"
                : apiStatus === "ok"      ? "bg-emerald-400"
                : "bg-red-400"
              }`} />
              <span className="font-mono text-[10px] text-white/40">
                {apiStatus === "checking" ? "API…" : apiStatus === "ok" ? "API" : "API ✕"}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-8 py-8 space-y-7">

        {/* Step bar */}
        <StepBar step={step} />

        {/* Error */}
        {step === "error" && (
          <div className="card px-7 py-5 border-alert/40 bg-red-50/60 flex items-start gap-4">
            <span className="text-alert font-black text-lg pt-0.5 shrink-0">!</span>
            <div>
              <p className="font-grotesk font-semibold text-nuit">Pipeline error</p>
              <p className="font-lora text-sm text-dusty mt-1">{error}</p>
              <button
                onClick={reset}
                className="mt-3 label-caps text-clinical hover:underline"
              >
                try again
              </button>
            </div>
          </div>
        )}

        {/* ── Step 1: Upload ── */}
        {step === "idle" && (
          <div className="space-y-5">

            {/* Brand hero */}
            <div className="flex items-center gap-5 py-2">
              <LogoMark size={52} />
              <div>
                <h1 className="font-grotesk font-black text-nuit text-2xl tracking-[0.08em] uppercase leading-none">
                  Ambient Scribe
                </h1>
                <p className="font-lora text-dusty text-sm mt-1.5 leading-snug">
                  Fully local clinical AI — audio consultation to FHIR R5 note,<br />
                  with mandatory clinician sign-off before anything is saved.
                </p>
              </div>
            </div>

            <div className="h-px bg-ruled" />

            {/* Patient context */}
            <div className="card px-7 py-5 space-y-4">
              <p className="label-caps">Patient Context</p>
              <div className="grid grid-cols-2 gap-6">
                {[
                  { id: "patient-ref",   label: "Patient reference",   val: patientRef,   set: setPatientRef,   autoComplete: "off" },
                  { id: "encounter-ref", label: "Encounter reference",  val: encounterRef, set: setEncounterRef, autoComplete: "off" },
                ].map(({ id, label, val, set, autoComplete }) => (
                  <div key={id}>
                    <label htmlFor={id} className="font-grotesk text-xs text-dusty block mb-1.5">
                      {label}
                    </label>
                    <input
                      id={id}
                      name={id}
                      type="text"
                      autoComplete={autoComplete}
                      value={val}
                      onChange={(e) => set(e.target.value)}
                      className="w-full border border-ruled rounded px-3 py-2 text-sm font-grotesk text-nuit bg-white outline-none focus-visible:border-clinical focus-visible:ring-2 focus-visible:ring-clinical/20 transition-colors"
                    />
                  </div>
                ))}
              </div>
            </div>

            <AudioUploader onFile={handleUploadAndGenerate} />
          </div>
        )}

        {/* ── Loading ── */}
        {step === "uploading" && <SpinnerCard title="Uploading recording…" />}
        {step === "generating" && (
          <SpinnerCard
            title="Running pipeline…"
            sub="Transcription → Speaker diarization → SOAP note generation"
          />
        )}

        {/* ── Step 2: Review ── */}
        {(step === "review" || step === "approving") && draft && editedNote && (
          <div className="space-y-5">

            {/* DRAFT banner — no border-radius, stamp-like */}
            <DraftBanner />

            {/* Meta row */}
            <div className="flex items-center gap-5 px-1">
              {[
                { label: "Patient",     val: draft.ctx.patient_ref    },
                { label: "Encounter",   val: draft.ctx.encounter_ref  },
                { label: "Utterances",  val: String(draft.dialogue.length) },
              ].map(({ label, val }, i) => (
                <span key={label} className="flex items-baseline gap-1.5">
                  {i > 0 && <span className="text-ruled mr-3">·</span>}
                  <span className="label-caps">{label}</span>
                  <span className="font-grotesk text-sm text-nuit">{val}</span>
                </span>
              ))}
            </div>

            {/* Split: Transcript | SOAP */}
            <div className="grid grid-cols-2 gap-5">
              <div className="card px-6 py-6">
                <p className="label-caps mb-5">Transcript</p>
                <TranscriptPane utterances={draft.dialogue} />
              </div>
              <div className="card px-6 py-6">
                <div className="flex items-center gap-2 mb-5">
                  <p className="label-caps">SOAP Note</p>
                  <span className="label-caps text-clinical/60">· editable</span>
                </div>
                <SOAPEditor note={editedNote} onChange={setEditedNote} />
              </div>
            </div>

            <ApproveSection onApprove={handleApprove} loading={step === "approving"} />
          </div>
        )}

        {/* ── Step 3: Done ── */}
        {step === "done" && docRef && (
          <div className="space-y-5">
            <div className="card px-7 py-6 border-emerald-300 bg-emerald-50/60 flex items-start gap-5">
              <div className="shrink-0 w-9 h-9 rounded-full bg-emerald-600 flex items-center justify-center text-white font-black text-sm">
                ✓
              </div>
              <div>
                <p className="font-grotesk font-bold text-emerald-900 text-base">
                  Note approved &amp; exported
                </p>
                <p className="font-lora text-sm text-emerald-800 mt-1 leading-relaxed">
                  A FHIR R5 DocumentReference has been generated and signed off. Nothing left
                  the draft state without your review.
                </p>
              </div>
            </div>

            <div className="card px-7 py-6">
              <div className="flex items-center gap-2 mb-4">
                <p className="label-caps">FHIR DocumentReference</p>
                <span className="label-caps text-dusty/50">· JSON</span>
              </div>
              <pre className="font-mono text-[12px] text-nuit/80 bg-vellum rounded p-4 overflow-auto max-h-96 leading-relaxed border border-ruled">
                {JSON.stringify(docRef.resource, null, 2)}
              </pre>
            </div>

            <button
              onClick={reset}
              className="label-caps text-clinical hover:underline"
            >
              ← new consultation
            </button>
          </div>
        )}

      </main>
    </div>
  );
}
