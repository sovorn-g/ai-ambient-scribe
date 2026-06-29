"use client";

import type { SOAPNote, Claim, SpanRef } from "@/lib/types";

interface Props {
  note: SOAPNote;
  onChange: (note: SOAPNote) => void;
  onHoverCitations: (citations: SpanRef[]) => void;
  onLeaveCitations: () => void;
  // Pin/navigate state (Phase-5b multi-cite navigation):
  //   pinnedLoc matches "${key}:${idx}" of the claim currently pinned.
  //   Clicking ◀/▶ pins (if not already) and cycles through every citation.
  //   ✕ unpins. The pin survives mouse-off so the arrows stay clickable.
  pinnedLoc: string | null;
  pinnedIdx: number;
  onCyclePinned: (loc: string, citations: SpanRef[], delta: number) => void;
  onUnpin: () => void;
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
  loc,
  pinnedLoc,
  pinnedIdx,
  onChange,
  onRemove,
  onHoverCitations,
  onLeaveCitations,
  onCyclePinned,
  onUnpin,
}: {
  claim: Claim;
  loc: string;
  pinnedLoc: string | null;
  pinnedIdx: number;
  onChange: (c: Claim) => void;
  onRemove: () => void;
  onHoverCitations: (citations: SpanRef[]) => void;
  onLeaveCitations: () => void;
  onCyclePinned: (loc: string, citations: SpanRef[], delta: number) => void;
  onUnpin: () => void;
}) {
  const citeCount = claim.citations.length;
  const isPinnedHere = pinnedLoc === loc;
  // When not pinned here, the preview shows the first cite (1). When pinned,
  // the navigator drives the index. This is the number rendered in ◀ 1/X ▶.
  const displayedIdx = isPinnedHere ? pinnedIdx + 1 : 1;

  return (
    <div
      className="group flex gap-2 items-start"
      // Mouse-only hover binding on the row. Focus handlers live on the
      // textarea itself (not the row) so that clicking a navigator button
      // doesn't re-fire onHoverCitations via focus-capture and override the
      // pinned cycle.
      onMouseEnter={() => onHoverCitations(claim.citations)}
      onMouseLeave={() => onLeaveCitations()}
    >
      <textarea
        rows={2}
        value={claim.text}
        onChange={(e) => onChange({ ...claim, text: e.target.value })}
        onFocus={() => onHoverCitations(claim.citations)}
        onBlur={() => onLeaveCitations()}
        className={`
          flex-1 font-lora text-[14px] text-nuit leading-relaxed resize-none
          bg-transparent border-0 border-b border-ruled
          px-0 py-1
          outline-none focus-visible:border-clinical focus-visible:ring-1 focus-visible:ring-clinical/30
          transition-colors
        `}
      />

      {/* Compact citation navigator — ◀ 1/X ▶ (✕ when pinned).
          • Hovering the row previews cite 1 in the transcript pane.
          • Click ◀/▶ to pin (sticky) and step through every cited utterance.
            The pin survives mouse-off so the arrows stay usable.
          • ✕ unpins. */}
      {citeCount > 0 && (
        <div
          className={`mt-1 shrink-0 flex items-center gap-0.5 font-mono text-[9px] tracking-widest uppercase px-1 py-0.5 rounded border transition-colors ${
            isPinnedHere
              ? "bg-amber-200 text-amber-900 border-amber-400"
              : "bg-amber-50 text-amber-700 border-amber-200"
          }`}
          role="group"
          aria-label={`Citation navigator, ${displayedIdx} of ${citeCount}`}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onCyclePinned(loc, claim.citations, -1);
            }}
            className="px-1 hover:text-amber-900 disabled:opacity-30 disabled:cursor-not-allowed"
            disabled={citeCount <= 1}
            aria-label="Previous citation"
            title="Previous citation"
          >
            ◀
          </button>
          <span className="tabular-nums px-0.5 select-none" title={`${displayedIdx} of ${citeCount} cited span${citeCount > 1 ? "s" : ""}`}>
            {displayedIdx}/{citeCount}
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onCyclePinned(loc, claim.citations, +1);
            }}
            className="px-1 hover:text-amber-900 disabled:opacity-30 disabled:cursor-not-allowed"
            disabled={citeCount <= 1}
            aria-label="Next citation"
            title="Next citation"
          >
            ▶
          </button>
          {isPinnedHere && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onUnpin();
              }}
              className="ml-0.5 px-1 hover:text-alert"
              aria-label="Unpin citation"
              title="Unpin"
            >
              ✕
            </button>
          )}
        </div>
      )}

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

export default function SOAPEditor({
  note,
  onChange,
  onHoverCitations,
  onLeaveCitations,
  pinnedLoc,
  pinnedIdx,
  onCyclePinned,
  onUnpin,
}: Props) {
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
                  loc={`${key}:${idx}`}
                  pinnedLoc={pinnedLoc}
                  pinnedIdx={pinnedIdx}
                  onChange={(c) => updateClaim(key, idx, c)}
                  onRemove={() => removeClaim(key, idx)}
                  onHoverCitations={onHoverCitations}
                  onLeaveCitations={onLeaveCitations}
                  onCyclePinned={onCyclePinned}
                  onUnpin={onUnpin}
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
