import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import CatalogueNav from "../components/CatalogueNav.jsx";
import ExportPanel from "../components/ExportPanel.jsx";
import { SeverityBadge, StatusBadge, label } from "../components/Badges.jsx";
import { errorMessage, getComparison } from "../services/api.js";

const val = (v) => (v === "" ? <em className="text-slate-400">(empty)</em> : <code className="whitespace-pre">{v}</code>);

function IssueTable({ issues, empty }) {
  if (issues.length === 0) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left text-xs uppercase text-slate-500">
          <tr><th className="px-3 py-2">Row</th><th className="px-3 py-2">SKU</th><th className="px-3 py-2">Column</th><th className="px-3 py-2">Issue</th><th className="px-3 py-2">Severity</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Value</th></tr>
        </thead>
        <tbody>
          {issues.map((i) => (
            <tr key={i.issue_id} className="border-t border-slate-100">
              <td className="px-3 py-1.5">{i.row_id + 1}</td>
              <td className="px-3 py-1.5">{i.sku || "—"}</td>
              <td className="px-3 py-1.5">{i.column}</td>
              <td className="px-3 py-1.5">{label(i.issue_type)}</td>
              <td className="px-3 py-1.5"><SeverityBadge severity={i.severity} /></td>
              <td className="px-3 py-1.5"><StatusBadge status={i.status} /></td>
              <td className="px-3 py-1.5">{val(i.current_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ComparisonPage() {
  const { catalogueId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getComparison(catalogueId).then(setData).catch((e) => setError(errorMessage(e)));
  }, [catalogueId]);

  return (
    <div>
      <CatalogueNav catalogueId={catalogueId} />
      <h1 className="mb-4 text-2xl font-semibold">Original vs corrected</h1>
      {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-700">{error}</p>}
      {!data && !error && <p className="text-slate-500">Loading…</p>}
      {data && (
        <div className="space-y-8">
          <ExportPanel catalogueId={catalogueId} data={data} />
          <section>
            <h2 className="mb-2 text-lg font-semibold">Changes applied ({data.changed_cells.length})</h2>
            {data.changed_cells.length === 0 ? (
              <p className="text-sm text-slate-500">No values have been changed. The working copy matches the original upload.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-100 text-left text-xs uppercase text-slate-500">
                    <tr><th className="px-3 py-2">Row</th><th className="px-3 py-2">SKU</th><th className="px-3 py-2">Column</th><th className="px-3 py-2">Original</th><th className="px-3 py-2">Corrected</th><th className="px-3 py-2">How</th></tr>
                  </thead>
                  <tbody>
                    {data.changed_cells.map((c) => (
                      <tr key={`${c.row_id}-${c.column}`} className="border-t border-slate-100">
                        <td className="px-3 py-1.5">{c.row_id + 1}</td>
                        <td className="px-3 py-1.5">{c.sku || "—"}</td>
                        <td className="px-3 py-1.5">{c.column}</td>
                        <td className="bg-red-50 px-3 py-1.5">{val(c.original_value)}</td>
                        <td className="bg-green-50 px-3 py-1.5">{val(c.current_value)}</td>
                        <td className="px-3 py-1.5">{c.review_actions.join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section>
            <h2 className="mb-2 text-lg font-semibold">Unresolved issues ({data.unresolved_issues.length})</h2>
            <IssueTable issues={data.unresolved_issues} empty="No unresolved issues." />
          </section>
          <section>
            <h2 className="mb-2 text-lg font-semibold">Rejected or ignored ({data.dismissed_issues.length})</h2>
            <p className="mb-2 text-xs text-slate-500">These values were intentionally left as they are.</p>
            <IssueTable issues={data.dismissed_issues} empty="None." />
          </section>
        </div>
      )}
    </div>
  );
}
