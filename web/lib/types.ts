export interface SpanRef {
  utterance_id: string;
  char_span: [number, number] | null;
}

export interface Claim {
  text: string;
  citations: SpanRef[];
}

export interface SOAPNote {
  subjective: Claim[];
  objective: Claim[];
  assessment: Claim[];
  plan: Claim[];
}

export interface TimeSpan {
  start: number;
  end: number;
}

export interface Utterance {
  id: string;
  role: "CLINICIAN" | "PATIENT" | "UNKNOWN";
  text: string;
  time_span: TimeSpan;
  speaker_id: string;
}

export interface PatientContext {
  patient_ref: string;
  encounter_ref: string;
  patient_display: string | null;
}

export interface DraftResponse {
  id: string;
  status: "DRAFT" | "APPROVED";
  ctx: PatientContext;
  dialogue: Utterance[];
  note: SOAPNote;
}

export interface DocumentRefResponse {
  resource: Record<string, unknown>;
  json_text: string;
}
