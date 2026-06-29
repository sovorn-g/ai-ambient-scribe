import type { DraftResponse, DocumentRefResponse, SOAPNote } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function uploadAudio(file: File): Promise<{ path: string; filename: string; size: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/audio/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function generateDraft(
  patientRef: string,
  encounterRef: string,
  audioPath: string
): Promise<DraftResponse> {
  const res = await fetch(`${API_BASE}/drafts/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patient_ref: patientRef,
      encounter_ref: encounterRef,
      audio_path: audioPath,
    }),
  });
  if (!res.ok) throw new Error(`Generate failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function getDraft(draftId: string): Promise<DraftResponse> {
  const res = await fetch(`${API_BASE}/drafts/${draftId}`);
  if (!res.ok) throw new Error(`Get draft failed: ${res.status}`);
  return res.json();
}

export async function editDraft(
  draftId: string,
  note: SOAPNote
): Promise<DraftResponse> {
  const res = await fetch(`${API_BASE}/drafts/${draftId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Edit failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function approveDraft(
  draftId: string,
  approverName: string,
  approverRole = "clinician"
): Promise<DocumentRefResponse> {
  const res = await fetch(`${API_BASE}/drafts/${draftId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver_name: approverName, approver_role: approverRole }),
  });
  if (!res.ok) throw new Error(`Approve failed: ${res.status} ${await res.text()}`);
  return res.json();
}
