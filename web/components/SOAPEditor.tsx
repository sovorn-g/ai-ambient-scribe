"use client";

import type { SOAPNote, Claim, SpanRef } from "@/lib/types";

interface Props {
  note: SOAPNote;
  onChange: (note: SOAPNote) => void;
  onHoverCitations: (citations: SpanRef[]) => void;
  onLeaveCitations: () => void;
  // Pin/navigate state (Phase-5b multi-cite navigation):
  //   pinnedLoc matches "${key}:${idx}" of the claim that's currently pinned.
  //   Clicking the "N cites" badge toggles the pin on/off for that claim.
  //   When pinned, an inline ◀ idx/total ▶ ✕ navigator appears beside the
  //   badge and survives mouse-off so the user can step through every cite.
  pinnedLoc: string | null;
  pinnedIdx: number;
  onTogglePin: (loc: string, citations: SpanRef[]) => void;
  onCyclePinned: (delta: number) => void;
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
  onTogglePin,
  onCyclePinned,
}: {
  claim: Claim;
  loc: string;
  pinnedLoc: string | null;
  pinnedIdx: number;
  onChange: (c: Claim) => void;
  onRemove: () => void;
  onHoverCitations: (citations: SpanRef[]) => void;
  onLeaveCitations: () => void;
  onTogglePin: (loc: string, citations: SpanRef[]) => void;
  onCyclePinned: (delta: number) => void;
}) {
  const citeCount = claim.citations.length;
  const isPinnedHere = pinnedLoc === loc;

  // Navigator buttons stop click propagation so pressing ◀/▶/✕ doesn't blur
  // the textarea in a way that interferes, and so the row's onMouseLeave
  // doesn't fire from the bubbling target. (They're inside the row, so leave
  // only fires when the pointer actually exits the row — fine. We still stop
  // propagation on toggle/cycle to keep the pin semantics explicit.)
  return (
    <div
      className="group flex gap-2 items-start"
      // Hover or keyboard focus on the claim fires the *transient* citation
      // preview. Pinning is a separate click affordance on the badge below.
      onMouseEnter={() => onHoverCitations(claim.citations)}
      onMouseLeave={() => onLeaveCitations()}
      onFocusCapture={() => onHoverCitations(claim.citations)}
      onBlurCapture={() => onLeaveCitations()}
    >
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

      {/* Citation provenance + navigator.
          • Not pinned: "N cites" badge — click to pin (sticky). Hovering the
            row still gives the transient first-cite preview.
          • Pinned here: badge + inline ◀ idx/total ▶ ✕. Arrows step through
            every citation in the claim; each step scrolls + highlights the
            matching utterance. ✕ unpins. The navigator survives mouse-off so
            the user can click the arrows without losing the binding. */}
      {citeCount > 0 && (
        <div className="mt-1 shrink-0 flex items-center gap-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onTogglePin(loc, claim.citations);
            }}
            className={`font-mono text-[9px] tracking-widest uppercase
                        px-1.5 py-0.5 rounded border transition-colors
                        ${
                          isPinnedHere
                            ? "bg-amber-200 text-amber-900 border-amber-400"
                            : "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
                        }`}
            title={
              isPinnedHere
                ? "Pinned — click to unpin"
                : `${citeCount} transcript span${citeCount > 1 ? "s" : ""} cited — click to pin & navigate`
            }
            aria-pressed={isPinnedHere}
            aria-label={`${citeCount} citation${citeCount > 1 ? "s" : ""}${
              isPinnedHere ? " (pinned)" : ""
            }`}
          >
            {citeCount} cite{citeCount > 1 ? "s" : ""}
          </button>

          {isPinnedHere && (
            <span
              className="flex items-center gap-0.5 font-mono text-[9px] tracking-widest uppercase
                         px-1 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200"
              role="group"
              aria-label={`Citation navigator, ${pinnedIdx + 1} of ${citeCount}`}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onCyclePinned(-1);
                }}
                className="px-1 hover:text-amber-900 disabled:opacity-30 disabled:cursor-not-allowed"
                disabled={citeCount <= 1}
                aria-label="Previous citation"
                title="Previous citation"
              >
                ◀
              </button>
              <span className="tabular-nums px-0.5 select-none">
                {pinnedIdx + 1}/{citeCount}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onCyclePinned(+1);
                }}
                className="px-1 hover:text-amber-900 disabled:opacity-30 disabled:cursor-not-allowed"
                disabled={citeCount <= 1}
                aria-label="Next citation"
                title="Next citation"
              >
                ▶
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onTogglePin(loc, claim.citations);
                }}
                className="ml-0.5 px-1 hover:text-alert"
                aria-label="Unpin citation"
                title="Unpin"
              >
                ✕
              </button>
            </span>
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
  onTogglePin,
  onCyclePinned,
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
                  onTogglePin={onTogglePin}
                  onCyclePinned={onCyclePinned}
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
