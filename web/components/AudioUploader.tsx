"use client";

import { useRef, useState, DragEvent, ChangeEvent } from "react";

interface Props {
  onFile: (file: File) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AudioUploader({ onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);

  function pick(file: File) {
    setSelected(file);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) pick(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) pick(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(true);
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
        Consultation Recording
      </h2>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragging(false)}
        className={`
          relative border-2 border-dashed rounded-xl px-8 py-12 text-center cursor-pointer transition-colors
          ${dragging
            ? "border-blue-400 bg-blue-50"
            : selected
            ? "border-emerald-300 bg-emerald-50"
            : "border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/40"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.m4a,.flac,.ogg"
          className="hidden"
          onChange={handleChange}
        />

        {selected ? (
          <div className="space-y-2">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-100 flex items-center justify-center text-2xl">
              🎵
            </div>
            <p className="font-semibold text-slate-800 text-sm">{selected.name}</p>
            <p className="text-xs text-slate-500">{formatBytes(selected.size)}</p>
            <p className="text-xs text-emerald-600 font-medium">Ready to process</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-slate-200 flex items-center justify-center text-2xl">
              📁
            </div>
            <div>
              <p className="font-semibold text-slate-700">Drop your audio file here</p>
              <p className="text-sm text-slate-500 mt-1">or click to browse</p>
            </div>
            <p className="text-xs text-slate-400">Accepted: .wav · .mp3 · .m4a · .flac</p>
          </div>
        )}
      </div>

      {selected && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => { setSelected(null); if (inputRef.current) inputRef.current.value = ""; }}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            ✕ Remove
          </button>
          <button
            onClick={() => onFile(selected)}
            className="bg-[#1B4F8A] hover:bg-[#153d6b] text-white font-semibold px-6 py-2.5 rounded-lg shadow-sm transition-colors text-sm"
          >
            Process Consultation →
          </button>
        </div>
      )}
    </div>
  );
}
