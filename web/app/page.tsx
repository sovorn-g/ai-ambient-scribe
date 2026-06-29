"use client";

import { useState } from "react";
import DraftBanner from "@/components/DraftBanner";
import TranscriptPane from "@/components/TranscriptPane";
import SOAPEditor from "@/components/SOAPEditor";
import AudioUploader from "@/components/AudioUploader";
import ApproveSection from "@/components/ApproveSection";
import { uploadAudio, generateDraft, editDraft, approveDraft } from "@/lib/api";
import type { DraftResponse, DocumentRefResponse, SOAPNote } from "@/lib/types";

type Step = "idle" | "uploading" | "generating" | "review" | "approving" | "done" | "error";

const STEPS = [
  { id: "idle",     label: "Upload"  },
  { id: "review",   label: "Review"  },
  { id: "done",     label: "Export"  },
] as const;

function stepIndex(step: Step): number {
  if (step === "idle" || step === "uploading" || step === "generating" || step === "error") return 0;
  if (step === "review" || step === "approving") return 1;
  return 2;
}

function StepIndicator({ step }: { step: Step }) {
  const current = stepIndex(step);
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((s, i) => (
        <div key={s.id} className="flex items-center">
          <div className="flex flex-col items-center gap-1">
            <div className={`
              w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors
              ${i < current ? "bg-emerald-500 text-white" : i === current ? "bg-[#1B4F8A] text-white" : "bg-slate-200 text-slate-400"}
            `}>
              {i < current ? "✓" : i + 1}
            </div>
            <span className={`text-xs font-medium ${i === current ? "text-[#1B4F8A]" : "text-slate-400"}`}>
              {s.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`h-0.5 w-16 mx-2 mb-4 transition-colors ${i < current ? "bg-emerald-400" : "bg-slate-200"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

function StatusCard({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
      <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-blue-50 flex items-center justify-center">
        <span className="animate-spin text-2xl inline-block">⚙</span>
      </div>
      <p className="font-semibold text-slate-700">{title}</p>
      {subtitle && <p className="text-sm text-slate-400 mt-1">{subtitle}</p>}
    </div>
  );
}

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-slate-500 text-sm">
      <span className="font-medium text-slate-700">{label}:</span> {value}
    </span>
  );
}

function SectionHeader({ title, badge }: { title: string; badge?: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <h2 className="text-sm font-bold text-slate-700 uppercase tracking-wider">{title}</h2>
      {badge && (
        <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">
          {badge}
        </span>
      )}
    </div>
  );
}

export default function Home() {
  const [patientRef, setPatientRef] = useState("patient-001");
  const [encounterRef, setEncounterRef] = useState("encounter-001");
  const [step, setStep] = useState<Step>("idle");
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [editedNote, setEditedNote] = useState<SOAPNote | null>(null);
  const [docRef, setDocRef] = useState<DocumentRefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      setError(e instanceof Error ? e.message : String(e));
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
      setError(e instanceof Error ? e.message : String(e));
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
    <div className="min-h-screen bg-slate-50">
      {/* Nav */}
      <nav className="bg-[#0F2442] text-white px-6 py-3.5 flex items-center justify-between sticky top-0 z-10 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center font-black text-sm select-none">
            AS
          </div>
          <div>
            <span className="text-base font-bold tracking-tight">Ambient Scribe</span>
            <span className="ml-2 text-xs text-slate-400">clinical AI</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {(["Fully Local", "M4 16GB", "FHIR R5"] as const).map((tag) => (
            <span key={tag} className="text-xs bg-slate-700 text-slate-300 px-2.5 py-1 rounded-full">
              {tag}
            </span>
          ))}
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Step indicator */}
        <div className="flex items-center justify-between">
          <StepIndicator step={step} />
        </div>

        {/* Error state */}
        {step === "error" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-start gap-4">
            <div className="shrink-0 w-9 h-9 rounded-full bg-red-100 flex items-center justify-center text-red-500 font-bold">
              !
            </div>
            <div className="flex-1">
              <p className="font-semibold text-red-800">Pipeline error</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button onClick={reset} className="mt-3 text-sm text-red-600 hover:underline font-medium">
                ← Try again
              </button>
            </div>
          </div>
        )}

        {/* Step 1: Upload */}
        {step === "idle" && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
                Patient Context
              </h2>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: "Patient Reference", value: patientRef, set: setPatientRef },
                  { label: "Encounter Reference", value: encounterRef, set: setEncounterRef },
                ].map(({ label, value, set }) => (
                  <label key={label} className="block">
                    <span className="text-xs font-medium text-slate-500">{label}</span>
                    <input
                      type="text"
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent"
                    />
                  </label>
                ))}
              </div>
            </div>
            <AudioUploader onFile={handleUploadAndGenerate} />
          </div>
        )}

        {/* Loading states */}
        {step === "uploading" && (
          <StatusCard title="Uploading audio…" />
        )}
        {step === "generating" && (
          <StatusCard
            title="Running pipeline…"
            subtitle="Transcription → Speaker diarization → SOAP note generation"
          />
        )}

        {/* Step 2: Review */}
        {(step === "review" || step === "approving") && draft && editedNote && (
          <div className="space-y-4">
            <DraftBanner />

            {/* Meta bar */}
            <div className="bg-white rounded-xl border border-slate-200 px-6 py-3 flex items-center gap-6">
              <MetaPill label="Patient" value={draft.ctx.patient_ref} />
              <div className="w-px h-4 bg-slate-200" />
              <MetaPill label="Encounter" value={draft.ctx.encounter_ref} />
              <div className="w-px h-4 bg-slate-200" />
              <MetaPill label="Utterances" value={String(draft.dialogue.length)} />
            </div>

            {/* Two-column: Transcript + SOAP */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <SectionHeader title="Transcript" />
                <TranscriptPane utterances={draft.dialogue} />
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <SectionHeader title="SOAP Note" badge="editable" />
                <SOAPEditor note={editedNote} onChange={setEditedNote} />
              </div>
            </div>

            <ApproveSection onApprove={handleApprove} loading={step === "approving"} />
          </div>
        )}

        {/* Step 3: Done */}
        {step === "done" && docRef && (
          <div className="space-y-4">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 flex items-start gap-4">
              <div className="shrink-0 w-11 h-11 rounded-full bg-emerald-500 flex items-center justify-center text-white text-lg font-bold">
                ✓
              </div>
              <div>
                <h2 className="text-lg font-bold text-emerald-800">Note Approved &amp; Exported</h2>
                <p className="text-sm text-emerald-700 mt-1">
                  A FHIR R5 DocumentReference has been generated and signed off. Nothing was saved without clinician approval.
                </p>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <SectionHeader title="FHIR DocumentReference" badge="JSON" />
              <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-4 overflow-auto max-h-96 whitespace-pre-wrap font-mono leading-relaxed">
                {JSON.stringify(docRef.resource, null, 2)}
              </pre>
            </div>

            <button
              onClick={reset}
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              ← Start new consultation
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
