import type { DraftResponse, DocumentRefResponse, SOAPNote } from "./types";

export type { DraftResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000").replace(/^http/, "ws");

// ── Ambient listening (Phase 7) ───────────────────────────────────────────────

export type AmbientEvent =
  | { type: "session_started"; session_id: string }
  | { type: "listening"; seconds: number; bytes_received: number }
  | { type: "finalizing" }
  | { type: "draft_ready"; draft: DraftResponse }
  | { type: "cancelled" }
  | { type: "error"; message: string };

export interface AmbientHandlers {
  onEvent: (e: AmbientEvent) => void;
  onClose?: () => void;
}

/**
 * Open the ambient listening WebSocket. Returns a controller to send commands
 * and binary chunks, and to close the socket.
 */
export function openAmbientSocket(handlers: AmbientHandlers): {
  start: (patientRef: string, encounterRef: string) => void;
  sendAudio: (pcm16: ArrayBuffer) => void;
  stop: () => void;
  cancel: () => void;
  close: () => void;
} {
  const ws = new WebSocket(`${WS_BASE}/ambient/ws`);
  ws.binaryType = "arraybuffer";
  let totalBytesSent = 0;
  let chunksSent = 0;
  ws.onopen = () => console.info("[ambient-ws] open →", WS_BASE);
  ws.onerror = (e) => console.error("[ambient-ws] error", e);
  ws.onclose = (e) => {
    console.info("[ambient-ws] close code=%d reason=%s sentChunks=%d sentBytes=%d",
      e.code, e.reason || "(empty)", chunksSent, totalBytesSent);
    handlers.onClose?.();
  };
  ws.onmessage = (e) => {
    if (typeof e.data !== "string") return;
    try {
      const evt = JSON.parse(e.data) as AmbientEvent;
      console.debug("[ambient-ws] recv", evt);
      handlers.onEvent(evt);
    } catch (err) {
      console.warn("[ambient-ws] malformed frame", err, e.data);
    }
  };

  const ensureOpen = (action: () => void) => {
    if (ws.readyState === WebSocket.OPEN) action();
    else ws.addEventListener("open", action, { once: true });
  };

  return {
    start: (patientRef, encounterRef) =>
      ensureOpen(() => {
        console.info("[ambient-ws] send start patient=%s encounter=%s", patientRef, encounterRef);
        ws.send(JSON.stringify({ type: "start", patient_ref: patientRef, encounter_ref: encounterRef, sample_rate: 16000 }));
      }),
    sendAudio: (pcm16) => {
      if (ws.readyState !== WebSocket.OPEN) {
        // Drop silently but log once-per-few so dropped-while-opening is visible.
        if ((chunksSent % 4) === 0) console.warn("[ambient-ws] drop chunk: socket not open (readyState=%d)", ws.readyState);
        return;
      }
      ws.send(pcm16);
      chunksSent++;
      totalBytesSent += pcm16.byteLength;
    },
    stop: () => ensureOpen(() => {
      console.info("[ambient-ws] send stop (sentChunks=%d sentBytes=%d)", chunksSent, totalBytesSent);
      ws.send(JSON.stringify({ type: "stop" }));
    }),
    cancel: () => ensureOpen(() => {
      console.info("[ambient-ws] send cancel");
      ws.send(JSON.stringify({ type: "cancel" }));
    }),
    close: () => ws.readyState <= WebSocket.OPEN && ws.close(),
  };
}

export async function checkHealth(): Promise<{ ok: boolean; scribe_ready: boolean } | null> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

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
