import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { downloadCsv, errorMessage } from "../services/api.js";

// Download buttons plus an honest summary: ignored/open issues are never described as fixed.
export default function ExportPanel({ catalogueId, data }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function download(kind) {
    setBusy(kind);
    setError("");
    try {
      await downloadCsv(catalogueId, kind);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  }

  const unresolved = data.unresolved_issues.length;
  const dismissed = data.dismissed_issues.length;
  const failing = data.unresolved_issues.filter((i) => i.revalidation_passed === false).length;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-lg font-semibold">Export</h2>
      <ul className="mb-3 space-y-1 text-sm text-slate-700">
        <li><strong>{data.changed_cells.length}</strong> value(s) changed from the original (approved or entered by you).</li>
        <li><strong>{data.resolved_count}</strong> issue(s) resolved.</li>
        <li className={unresolved ? "text-amber-700" : ""}>
          <strong>{unresolved}</strong> issue(s) still unresolved
          {failing > 0 && <> ({failing} changed but still failing a check)</>}.
        </li>
        <li><strong>{dismissed}</strong> issue(s) rejected or ignored — left as they are.</li>
      </ul>
      {unresolved + dismissed > 0 && (
        <p className="mb-3 rounded-md bg-amber-50 p-2 text-xs text-amber-800">
          This catalogue is not fully clean. The cleaned CSV contains only the changes listed above; the
          quality report lists every issue with its decision and status.
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button onClick={() => download("export")} disabled={!!busy} className="btn-primary">
          {busy === "export" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          Download cleaned CSV
        </button>
        <button onClick={() => download("report")} disabled={!!busy} className="btn">
          {busy === "report" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          Download quality report
        </button>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Cells that begin with =, +, - or @ (other than plain numbers) are prefixed with an apostrophe so spreadsheets
        cannot run them as formulas.
      </p>
      {error && <p role="alert" className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
    </section>
  );
}
