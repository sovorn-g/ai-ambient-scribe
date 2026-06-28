"use client";

export default function DraftBanner() {
  return (
    <div className="bg-red-600 text-white px-6 py-4 rounded-lg shadow-lg border-2 border-red-800 flex items-center gap-3">
      <span className="text-2xl font-black tracking-widest">⚠ DRAFT</span>
      <span className="text-lg font-semibold">
        This note has NOT been approved. Requires clinician review and sign-off before use.
      </span>
    </div>
  );
}
