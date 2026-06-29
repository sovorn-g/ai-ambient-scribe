"use client";

import type { Utterance } from "@/lib/types";

interface Props {
  utterances: Utterance[];
}

const ROLE_CONFIG: Record<string, { label: string; pill: string; bubble: string }> = {
  CLINICIAN: {
    label: "Clinician",
    pill: "bg-blue-100 text-blue-700 border border-blue-200",
    bubble: "bg-blue-50 border-blue-100",
  },
  PATIENT: {
    label: "Patient",
    pill: "bg-violet-100 text-violet-700 border border-violet-200",
    bubble: "bg-violet-50 border-violet-100",
  },
  UNKNOWN: {
    label: "Unknown",
    pill: "bg-slate-100 text-slate-500 border border-slate-200",
    bubble: "bg-slate-50 border-slate-100",
  },
};

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m > 0 ? `${m}:${sec.toString().padStart(2, "0")}` : `${sec}s`;
}

export default function TranscriptPane({ utterances }: Props) {
  if (utterances.length === 0) {
    return (
      <p className="text-slate-400 italic text-sm text-center py-8">
        No transcript available.
      </p>
    );
  }

  return (
    <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
      {utterances.map((u) => {
        const cfg = ROLE_CONFIG[u.role] ?? ROLE_CONFIG.UNKNOWN;
        return (
          <div key={u.id} className={`rounded-lg border p-3 ${cfg.bubble}`}>
            <div className="flex items-center justify-between mb-1.5">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${cfg.pill}`}>
                {cfg.label}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                {formatTime(u.time_span.start)} – {formatTime(u.time_span.end)}
              </span>
            </div>
            <p className="text-sm text-slate-800 leading-relaxed">{u.text}</p>
          </div>
        );
      })}
    </div>
  );
}
