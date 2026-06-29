"use client";

import { useState } from "react";

interface Props {
  onApprove: (approverName: string) => void;
  loading: boolean;
}

export default function ApproveSection({ onApprove, loading }: Props) {
  const [name, setName] = useState("");

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div className="flex-1">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
            Clinician Sign-off
          </label>
          <input
            type="text"
            placeholder="Enter your full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent disabled:bg-slate-50 disabled:text-slate-400"
          />
        </div>
        <button
          onClick={() => name.trim() && onApprove(name.trim())}
          disabled={!name.trim() || loading}
          className={`
            shrink-0 flex items-center gap-2 px-6 py-2.5 rounded-lg font-semibold text-sm shadow-sm transition-all
            ${!name.trim() || loading
              ? "bg-slate-200 text-slate-400 cursor-not-allowed"
              : "bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white shadow-emerald-200 shadow-md"
            }
          `}
        >
          {loading ? (
            <>
              <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Approving…
            </>
          ) : (
            <>✓ Approve &amp; Export to FHIR</>
          )}
        </button>
      </div>
      <p className="text-xs text-slate-400 mt-3">
        By approving, you confirm this note is clinically accurate. This action creates a signed FHIR DocumentReference.
      </p>
    </div>
  );
}
