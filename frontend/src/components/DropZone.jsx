import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

const MAX_MB = 10;

export default function DropZone({ onFile, disabled, progress }) {
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState("");

  function handle(file) {
    setError("");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) return setError("Please choose a .csv file.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`File is larger than ${MAX_MB} MB.`);
    if (file.size === 0) return setError("The file is empty.");
    onFile(file);
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); !disabled && handle(e.dataTransfer.files[0]); }}
        className={`flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-12 text-center transition ${
          over ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white hover:border-indigo-400"
        } ${disabled ? "cursor-wait opacity-60" : ""}`}
      >
        <UploadCloud className="h-10 w-10 text-indigo-600" />
        <p className="font-medium">Drag and drop a product catalogue CSV, or click to browse</p>
        <p className="text-sm text-slate-500">Up to {MAX_MB} MB. Your original file is never modified.</p>
        {disabled && (
          <p className="text-sm text-indigo-600">
            {progress < 100 ? `Uploading… ${progress}%` : "Processing…"}
          </p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => { handle(e.target.files[0]); e.target.value = ""; }}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
