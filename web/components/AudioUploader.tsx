"use client";

import { useRef, useState, DragEvent, ChangeEvent } from "react";

interface Props {
  onFile: (file: File) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AudioUploader({ onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);

  function pick(file: File) { setSelected(file); }
  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) pick(f);
  }
  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pick(f);
  }

  return (
    <div className="card p-7 space-y-6">
      <p className="label-caps">Consultation Recording</p>

      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        className={`
          relative border-2 border-dashed rounded-md
          flex flex-col items-center justify-center gap-3
          py-14 cursor-pointer select-none transition-colors
          ${dragging
            ? "border-clinical bg-clinical/5"
            : selected
            ? "border-emerald-400 bg-emerald-50/50"
            : "border-ruled hover:border-dusty bg-vellum/60"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.m4a,.flac,.ogg"
          className="sr-only"
          onChange={handleChange}
        />

        {selected ? (
          <>
            <span className="text-3xl">🎵</span>
            <div className="text-center">
              <p className="font-grotesk font-semibold text-nuit text-sm">{selected.name}</p>
              <p className="font-mono text-xs text-dusty mt-0.5">{formatBytes(selected.size)}</p>
            </div>
            <span className="label-caps text-emerald-600">Ready</span>
          </>
        ) : (
          <>
            <span className="text-3xl text-dusty/50">↑</span>
            <div className="text-center">
              <p className="font-grotesk font-medium text-nuit text-sm">
                Drop audio file or <span className="text-clinical underline underline-offset-2">browse</span>
              </p>
              <p className="font-mono text-xs text-dusty mt-1 tracking-wide">
                .wav · .mp3 · .m4a · .flac
              </p>
            </div>
          </>
        )}
      </div>

      <div className="flex items-center justify-between">
        {selected ? (
          <button
            onClick={() => { setSelected(null); if (inputRef.current) inputRef.current.value = ""; }}
            className="label-caps text-dusty hover:text-alert transition-colors"
          >
            remove file
          </button>
        ) : <span />}

        <button
          onClick={() => selected && onFile(selected)}
          disabled={!selected}
          className="bg-clinical text-white font-grotesk font-semibold text-sm px-7 py-2.5 rounded shadow-sm transition-colors hover:bg-[#153d6b] disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
        >
          Process consultation →
        </button>
      </div>
    </div>
  );
}
