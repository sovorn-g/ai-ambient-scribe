"use client";

import type { SOAPNote, Claim } from "@/lib/types";

interface Props {
  note: SOAPNote;
  onChange: (note: SOAPNote) => void;
}

const SECTIONS: Array<{
  key:    keyof SOAPNote;
  letter: string;
  title:  string;
  accent: string;
}> = [
  { key: "subjective", letter: "S", title: "Subjective",  accent: "border-clinical text-clinical"       },
  { key: "objective",  letter: "O", title: "Objective",   accent: "border-purple-500 text-purple-700"   },
  { key: "assessment", letter: "A", title: "Assessment",  accent: "border-amber-500 text-amber-700"     },
  { key: "plan",       letter: "P", title: "Plan",        accent: "border-emerald-600 text-emerald-700" },
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
    <div className="group flex gap-2 items-start">
      <textarea
        rows={2}
        value={claim.text}
        onChange={(e) => onChange({ ...claim, text: e.target.value })}
        className={`
          flex-1 font-lora text-[14px] text-nuit leading-relaxed resize-none
          bg-transparent border-0 border-b border-ruled
          px-0 py-1
          outline-none focus-visible:border-clinical focus-visible:ring-1 focus-visible:ring-clinical/30
          transition-colors
        `}
      />
      <button
        onClick={onRemove}
        aria-label="Remove entry"
        className="opacity-0 group-hover:opacity-100 transition-opacity text-dusty hover:text-alert text-xs pt-2 px-1 shrink-0"
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
    <div className="space-y-7 overflow-y-auto max-h-[500px] pr-2">
      {SECTIONS.map(({ key, letter, title, accent }) => {
        const [borderClass, textClass] = accent.split(" ");
        return (
          <div key={key}>
            <div className={`flex items-baseline gap-2.5 mb-3 border-b pb-1.5 ${borderClass}`}>
              <span className={`font-grotesk font-black text-xl leading-none ${textClass}`}>
                {letter}
              </span>
              <span className="label-caps">{title}</span>
            </div>

            <div className="space-y-2 pl-1">
              {note[key].length === 0 && (
                <p className="font-lora italic text-dusty/70 text-sm">No entries.</p>
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
              className="mt-2 label-caps text-dusty hover:text-clinical transition-colors"
            >
              + add entry
            </button>
          </div>
        );
      })}
    </div>
  );
}
