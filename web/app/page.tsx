"use client";

import { useState } from "react";
import DraftBanner from "@/components/DraftBanner";
import TranscriptPane from "@/components/TranscriptPane";
import SOAPEditor from "@/components/SOAPEditor";
import ApproveButton from "@/components/ApproveButton";
import { generateDraft, editDraft, approveDraft } from "@/lib/api";
import type { DraftResponse, DocumentRefResponse, SOAPNote } from "@/lib/types";

type Step = "idle" | "generating" | "review" | "approving" | "done" | "error";

export default function Home() {
  const [audioPath, setAudioPath] = useState("");
  const [patientRef, setPatientRef] = useState("patient-001");
  const [encounterRef, setEncounterRef] = useState("encounter-001");

  const [step, setStep] = useState<Step>("idle");
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [editedNote, setEditedNote] = useState<SOAPNote | null>(null);
  const [docRef, setDocRef] = useState<DocumentRefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!audioPath.trim()) {
      setError("Please enter an audio file path.");
      return;
    }
    setError(null);
    setStep("generating");
    try {
      const d = await generateDraft(patientRef, encounterRef, audioPath);
      setDraft(d);
      setEditedNote(d.note);
      setStep("review");
    } catch (e: unknown) {
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setStep("error");
    }
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-3xl font-bold text-gray-900">Ambient Scribe</h1>
        <span className="text-sm text-gray-500">fully-local · M4 · FHIR R5</span>
      </div>

      {/* Input panel */}
      {(step === "idle" || step === "error") && (
        <div className="bg-white rounded-xl shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Generate Draft Note</h2>
          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Patient Ref</span>
              <input
                type="text"
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                value={patientRef}
                onChange={(e) => setPatientRef(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Encounter Ref</span>
              <input
                type="text"
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                value={encounterRef}
                onChange={(e) => setEncounterRef(e.target.value)}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Audio File Path</span>
            <input
              type="text"
              placeholder="/path/to/consult.wav"
              className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={audioPath}
              onChange={(e) => setAudioPath(e.target.value)}
            />
          </label>
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}
          <button
            onClick={handleGenerate}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg shadow transition-colors"
          >
            Generate Draft
          </button>
        </div>
      )}

      {step === "generating" && (
        <div className="bg-white rounded-xl shadow p-8 text-center text-gray-500">
          <div className="animate-spin text-4xl mb-3">⚙</div>
          <p>Running pipeline: transcription → diarization → note generation…</p>
        </div>
      )}

      {(step === "review" || step === "approving") && draft && editedNote && (
        <>
          <DraftBanner />

          <div className="grid grid-cols-2 gap-6">
            {/* Left: Transcript */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-base font-semibold text-gray-800 mb-4">
                Transcript
                <span className="ml-2 text-xs text-gray-400 font-normal">
                  {draft.dialogue.length} utterances
                </span>
              </h2>
              <TranscriptPane utterances={draft.dialogue} />
            </div>

            {/* Right: SOAP editor */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-base font-semibold text-gray-800 mb-4">
                SOAP Note
                <span className="ml-2 text-xs text-gray-400 font-normal">editable</span>
              </h2>
              <SOAPEditor note={editedNote} onChange={setEditedNote} />
            </div>
          </div>

          <div className="bg-white rounded-xl shadow p-6 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              <span className="font-medium">Patient:</span> {draft.ctx.patient_ref} &nbsp;·&nbsp;
              <span className="font-medium">Encounter:</span> {draft.ctx.encounter_ref}
            </div>
            <ApproveButton
              onApprove={handleApprove}
              loading={step === "approving"}
            />
          </div>
        </>
      )}

      {step === "done" && docRef && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-300 rounded-xl p-6">
            <h2 className="text-lg font-bold text-green-800 mb-1">✓ Note Approved & Exported</h2>
            <p className="text-sm text-green-700">
              FHIR R5 DocumentReference generated. The note has been signed off by a clinician.
            </p>
          </div>
          <div className="bg-white rounded-xl shadow p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">FHIR DocumentReference (JSON)</h3>
            <pre className="text-xs bg-gray-50 border border-gray-200 rounded p-4 overflow-auto max-h-96 whitespace-pre-wrap">
              {JSON.stringify(docRef.resource, null, 2)}
            </pre>
          </div>
          <button
            onClick={() => {
              setStep("idle");
              setDraft(null);
              setEditedNote(null);
              setDocRef(null);
              setError(null);
              setAudioPath("");
            }}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Start new consultation
          </button>
        </div>
      )}
    </main>
  );
}
