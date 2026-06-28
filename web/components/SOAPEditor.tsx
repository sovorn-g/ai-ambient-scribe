"use client";

import { useState } from "react";
import type { SOAPNote, Claim } from "@/lib/types";

interface Props {
  note: SOAPNote;
  onChange: (note: SOAPNote) => void;
}

const SECTIONS: Array<{ key: keyof SOAPNote; label: string }> = [
  { key: "subjective", label: "S — Subjective" },
  { key: "objective", label: "O — Objective" },
  { key: "assessment", label: "A — Assessment" },
  { key: "plan", label: "P — Plan" },
];

function ClaimEditor({
  claim,
  onChange,
  onRemove,
}: {
  claim: Claim;
  onChange: (c: Claim) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex gap-2 items-start">
      <textarea
        className="flex-1 text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
        rows={2}
        value={claim.text}
        onChange={(e) => onChange({ ...claim, text: e.target.value })}
      />
      <button
        onClick={onRemove}
        className="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded mt-1"
        title="Remove claim"
      >
        ✕
      </button>
    </div>
  );
}

export default function SOAPEditor({ note, onChange }: Props) {
  function updateSection(key: keyof SOAPNote, claims: Claim[]) {
    onChange({ ...note, [key]: claims });
  }

  function updateClaim(key: keyof SOAPNote, idx: number, updated: Claim) {
    const claims = note[key].map((c, i) => (i === idx ? updated : c));
    updateSection(key, claims);
  }

  function removeClaim(key: keyof SOAPNote, idx: number) {
    updateSection(
      key,
      note[key].filter((_, i) => i !== idx)
    );
  }

  function addClaim(key: keyof SOAPNote) {
    updateSection(key, [...note[key], { text: "", citations: [] }]);
  }

  return (
    <div className="space-y-6">
      {SECTIONS.map(({ key, label }) => (
        <div key={key}>
          <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-2">
            {label}
          </h3>
          <div className="space-y-2">
            {note[key].length === 0 && (
              <p className="text-xs text-gray-400 italic">No entries.</p>
            )}
            {note[key].map((claim, idx) => (
              <ClaimEditor
                key={idx}
                claim={claim}
                onChange={(c) => updateClaim(key, idx, c)}
                onRemove={() => removeClaim(key, idx)}
              />
            ))}
          </div>
          <button
            onClick={() => addClaim(key)}
            className="mt-2 text-xs text-blue-500 hover:text-blue-700 font-medium"
          >
            + Add entry
          </button>
        </div>
      ))}
    </div>
  );
}
