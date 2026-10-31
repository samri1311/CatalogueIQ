import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Play } from "lucide-react";
import DropZone from "../components/DropZone.jsx";
import PreviewTable from "../components/PreviewTable.jsx";
import ColumnMapping from "../components/ColumnMapping.jsx";
import { analyzeCatalogue, errorMessage, uploadCatalogue } from "../services/api.js";

export default function UploadPage() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [upload, setUpload] = useState(null);
  const [mapping, setMapping] = useState({});

  async function onFile(file) {
    setError("");
    setBusy(true);
    setProgress(0);
    try {
      const data = await uploadCatalogue(file, setProgress);
      setUpload(data);
      setMapping(data.suggested_mapping);
    } catch (e) {
      setUpload(null);
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function setField(field, column) {
    setMapping((m) => {
      const next = { ...m };
      if (column) next[field] = column;
      else delete next[field];
      return next;
    });
  }

  async function runAnalysis() {
    setError("");
    setBusy(true);
    try {
      await analyzeCatalogue(upload.catalogue_id, mapping);
      navigate(`/catalogue/${upload.catalogue_id}/dashboard`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  const missingRequired = upload ? upload.required_fields.filter((f) => !mapping[f]) : [];

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-1 text-2xl font-semibold">Upload a catalogue</h1>
        <p className="mb-4 text-slate-600">
          CatalogueIQ checks your product data and suggests corrections. Nothing is changed
          without your approval.
        </p>
        <DropZone onFile={onFile} disabled={busy} progress={progress} />
        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
        )}
      </section>

      {upload && (
        <>
          <section>
            <h2 className="mb-2 text-lg font-semibold">
              Preview — {upload.filename}{" "}
              <span className="text-sm font-normal text-slate-500">
                ({upload.row_count} rows, showing first {upload.preview.length})
              </span>
            </h2>
            <PreviewTable columns={upload.columns} rows={upload.preview} />
          </section>

          <section>
            <h2 className="mb-1 text-lg font-semibold">Column mapping</h2>
            <p className="mb-3 text-sm text-slate-600">
              Match your columns to CatalogueIQ fields. Unmapped columns are kept and exported unchanged.
            </p>
            <ColumnMapping
              columns={upload.columns}
              standardFields={upload.standard_fields}
              requiredFields={upload.required_fields}
              mapping={mapping}
              onChange={setField}
            />
            {missingRequired.length > 0 && (
              <p className="mt-3 text-sm text-amber-700">
                Required but not mapped: {missingRequired.join(", ")}. Checks for these fields will be skipped.
              </p>
            )}
            <button
              onClick={runAnalysis}
              disabled={busy}
              className="mt-5 inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run quality checks
            </button>
          </section>
        </>
      )}
    </div>
  );
}
