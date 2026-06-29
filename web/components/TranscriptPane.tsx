"use client";

import type { Utterance } from "@/lib/types";

interface Props {
  utterances: Utterance[];
}

const roleStyle: Record<string, string> = {
  CLINICIAN: "bg-blue-100 text-blue-800",
  PATIENT: "bg-green-100 text-green-800",
  UNKNOWN: "bg-gray-100 text-gray-600",
};

export default function TranscriptPane({ utterances }: Props) {
  if (utterances.length === 0) {
    return <p className="text-gray-400 italic">No transcript available.</p>;
  }

  return (
    <div className="space-y-3">
      {utterances.map((u) => (
        <div key={u.id} className="flex gap-3 items-start">
          <span
            className={`text-xs font-bold px-2 py-1 rounded shrink-0 mt-0.5 ${roleStyle[u.role] ?? roleStyle.UNKNOWN}`}
          >
            {u.role}
          </span>
          <div className="flex-1">
            <p className="text-sm text-gray-800">{u.text}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {u.time_span.start.toFixed(1)}s – {u.time_span.end.toFixed(1)}s
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
