"use client";

import type { SOAPNote, Claim } from "@/lib/types";

interface Props {
  note: SOAPNote;
  onChange: (note: SOAPNote) => void;
}

const SECTIONS: Array<{
  key: keyof SOAPNote;
  label: string;
  accent: string;
  dot: string;
}> = [
  { key: "subjective",  label: "Subjective",  accent: "border-blue-400",   dot: "bg-blue-400"   },
  { key: "objective",   label: "Objective",   accent: "border-purple-400", dot: "bg-purple-400" },
  { key: "assessment",  label: "Assessment",  accent: "border-amber-400",  dot: "bg-amber-400"  },
  { key: "plan",        label: "Plan",        accent: "border-emerald-400",dot: "bg-emerald-400"},
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
    <div className="flex gap-2 items-start group">
      <textarea
        className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent resize-none bg-white leading-relaxed"
        rows={2}
        value={claim.text}
        onChange={(e) => onChange({ ...claim, text: e.target.value })}
      />
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 mt-1.5 text-slate-300 hover:text-red-400 transition-opacity px-1.5 py-1 rounded"
        title="Remove"
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
    updateSection(key, note[key].map((c, i) => (i === idx ? updated : c)));
  }

  function removeClaim(key: keyof SOAPNote, idx: number) {
    updateSection(key, note[key].filter((_, i) => i !== idx));
  }

  function addClaim(key: keyof SOAPNote) {
    updateSection(key, [...note[key], { text: "", citations: [] }]);
  }

  return (
    <div className="space-y-5 max-h-[520px] overflow-y-auto pr-1">
      {SECTIONS.map(({ key, label, accent, dot }) => (
        <div key={key} className={`border-l-4 pl-4 ${accent}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${dot}`} />
            <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
              {label}
            </h3>
          </div>
          <div className="space-y-2">
            {note[key].length === 0 && (
              <p className="text-xs text-slate-400 italic py-1">No entries.</p>
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
            className="mt-2 text-xs text-slate-400 hover:text-blue-500 font-medium transition-colors"
          >
            + Add entry
          </button>
        </div>
      ))}
    </div>
  );
}
