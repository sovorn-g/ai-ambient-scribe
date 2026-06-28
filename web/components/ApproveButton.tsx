"use client";

interface Props {
  onApprove: (approverName: string) => void;
  loading: boolean;
  disabled?: boolean;
}

export default function ApproveButton({ onApprove, loading, disabled }: Props) {
  function handleClick() {
    const name = window.prompt("Enter your name to sign off on this note:");
    if (name && name.trim()) {
      onApprove(name.trim());
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled || loading}
      className={`px-6 py-3 rounded-lg font-bold text-white text-base shadow transition-colors
        ${disabled || loading
          ? "bg-gray-400 cursor-not-allowed"
          : "bg-green-600 hover:bg-green-700 active:bg-green-800"
        }`}
    >
      {loading ? "Approving…" : "✓ Approve & Export to FHIR"}
    </button>
  );
}
