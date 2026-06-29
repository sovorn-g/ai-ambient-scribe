"use client";

import { useState } from "react";

interface Props {
  onApprove: (name: string) => void;
  loading: boolean;
}

export default function ApproveSection({ onApprove, loading }: Props) {
  const [name, setName] = useState("");
  const ready = name.trim().length > 0 && !loading;

  return (
    <div className="card px-8 py-6">
      <p className="label-caps mb-4">Clinician Sign-off</p>

      <div className="flex flex-col sm:flex-row items-end gap-6">
        <div className="flex-1 w-full">
          <label className="block text-xs text-dusty mb-1.5 font-grotesk" htmlFor="approver-name">
            Full name
          </label>
          {/* Underline-only input — signature line aesthetic */}
          <input
            id="approver-name"
            name="clinician-name"
            type="text"
            autoComplete="name"
            placeholder="Dr. Jane Smith"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ready && onApprove(name.trim())}
            disabled={loading}
            className="input-underline w-full text-base"
          />
        </div>

        <button
          onClick={() => ready && onApprove(name.trim())}
          disabled={!ready}
          aria-busy={loading}
          className={`
            shrink-0 flex items-center gap-2 font-grotesk font-semibold text-sm
            px-7 py-2.5 rounded transition-colors
            ${ready
              ? "bg-emerald-700 text-white hover:bg-emerald-800 shadow-sm"
              : "bg-ruled text-dusty cursor-not-allowed"
            }
          `}
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin motion-reduce:animate-none" />
              Approving…
            </>
          ) : (
            "✓ Approve & export to FHIR"
          )}
        </button>
      </div>

      <p className="font-lora text-[13px] text-dusty mt-4 leading-relaxed">
        By approving, you attest this note is clinically accurate. A signed FHIR R5
        DocumentReference will be generated — this action cannot be undone.
      </p>
    </div>
  );
}
