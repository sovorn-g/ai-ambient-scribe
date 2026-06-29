"use client";

export default function DraftBanner() {
  return (
    <div className="flex items-center gap-4 bg-red-700 text-white px-6 py-4 rounded-xl shadow-lg">
      <div className="shrink-0 w-10 h-10 rounded-full bg-red-500 border-2 border-red-300 flex items-center justify-center text-xl font-black">
        !
      </div>
      <div>
        <p className="text-base font-black tracking-wide uppercase">
          Draft — Not Approved
        </p>
        <p className="text-sm text-red-200 mt-0.5">
          This AI-generated note has not been reviewed. It must not be used for clinical decisions without clinician sign-off.
        </p>
      </div>
    </div>
  );
}
