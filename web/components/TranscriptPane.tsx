"use client";

import { useEffect, useRef } from "react";
import type { Utterance, SpanRef } from "@/lib/types";

interface Props {
  utterances: Utterance[];
  activeCitation: SpanRef | null;
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

// Split utterance text into [before, span, after] when char_span is in range.
// Returns null if the span is missing or out of bounds → caller falls back to
// whole-utterance tint.
function splitSpan(text: string, span: [number, number] | null) {
  if (!span) return null;
  const [start, end] = span;
  if (start < 0 || end > text.length || start >= end) return null;
  return { before: text.slice(0, start), mark: text.slice(start, end), after: text.slice(end) };
}

function UtteranceRow({
  utterance,
  activeCitation,
}: {
  utterance: Utterance;
  activeCitation: SpanRef | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isActive = activeCitation?.utterance_id === utterance.id;
  const span = isActive ? activeCitation?.char_span ?? null : null;
  const parts = span ? splitSpan(utterance.text, span) : null;

  // Auto-scroll the *first* active utterance into view on activation.
  // The "first" guarantee is enforced by the parent: it passes a single
  // activeCitation at a time (the first citation of the hovered claim),
  // so only one row ever matches per activation.
  useEffect(() => {
    if (isActive && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isActive, activeCitation]);

  const role = ROLE[utterance.role] ?? ROLE.UNKNOWN;
  const isClinic = utterance.role === "CLINICIAN";

  return (
    <div ref={ref} data-utterance-id={utterance.id}>
      <div className="flex items-baseline gap-3 mb-1">
        <span className={`label-caps ${role.color}`}>{role.label}</span>
        <span className="font-mono text-[10px] text-dusty/70">
          {formatTime(utterance.time_span.start)} – {formatTime(utterance.time_span.end)}
        </span>
        {isActive && (
          <span
            className="font-mono text-[9px] tracking-widest uppercase px-1.5 py-0.5 rounded
                       bg-amber-100 text-amber-800 border border-amber-300"
            title="Evidence cited by the hovered SOAP claim"
          >
            cited
          </span>
        )}
      </div>
      <div
        className={`pl-3 border-l-2 transition-colors ${
          isClinic ? "border-clinical/40" : "border-purple-300"
        } ${isActive ? "bg-amber-50 -mx-2 px-2 rounded-r" : ""}`}
      >
        {parts ? (
          <p className="font-lora text-[14.5px] text-nuit leading-relaxed">
            {parts.before}
            <mark className="bg-amber-200/80 text-nuit rounded px-0.5">{parts.mark}</mark>
            {parts.after}
          </p>
        ) : (
          <p className="font-lora text-[14.5px] text-nuit leading-relaxed">{utterance.text}</p>
        )}
      </div>
    </div>
  );
}

export default function TranscriptPane({ utterances, activeCitation }: Props) {
  if (utterances.length === 0) {
    return (
      <p className="font-lora italic text-dusty text-sm text-center py-10">
        No transcript available.
      </p>
    );
  }

  return (
    <div className="space-y-5 overflow-y-auto max-h-[500px] pr-2">
      {utterances.map((u) => (
        <UtteranceRow
          key={u.id}
          utterance={u}
          activeCitation={activeCitation}
        />
      ))}
    </div>
  );
}
