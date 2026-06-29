"use client";

import type { Utterance } from "@/lib/types";

interface Props {
  utterances: Utterance[];
}

const ROLE: Record<string, { label: string; color: string }> = {
  CLINICIAN: { label: "Clinician", color: "text-clinical" },
  PATIENT:   { label: "Patient",   color: "text-purple-700" },
  UNKNOWN:   { label: "Unknown",   color: "text-dusty"     },
};

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m > 0 ? `${m}:${sec.toString().padStart(2, "0")}` : `0:${sec.toString().padStart(2, "0")}`;
}

export default function TranscriptPane({ utterances }: Props) {
  if (utterances.length === 0) {
    return (
      <p className="font-lora italic text-dusty text-sm text-center py-10">
        No transcript available.
      </p>
    );
  }

  return (
    <div className="space-y-5 overflow-y-auto max-h-[500px] pr-2">
      {utterances.map((u, i) => {
        const role = ROLE[u.role] ?? ROLE.UNKNOWN;
        const isClinic = u.role === "CLINICIAN";
        return (
          <div key={u.id}>
            <div className="flex items-baseline gap-3 mb-1">
              <span className={`label-caps ${role.color}`}>{role.label}</span>
              <span className="font-mono text-[10px] text-dusty/70">
                {formatTime(u.time_span.start)} – {formatTime(u.time_span.end)}
              </span>
            </div>
            <div className={`pl-3 border-l-2 ${isClinic ? "border-clinical/40" : "border-purple-300"}`}>
              <p className="font-lora text-[14.5px] text-nuit leading-relaxed">{u.text}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
