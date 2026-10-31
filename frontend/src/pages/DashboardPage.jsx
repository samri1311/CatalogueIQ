import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import CatalogueNav from "../components/CatalogueNav.jsx";
import { label } from "../components/Badges.jsx";
import { errorMessage, getSummary } from "../services/api.js";

function Stat({ title, value, tone }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className={`text-2xl font-semibold ${tone || ""}`}>{value}</div>
      <div className="text-sm text-slate-500">{title}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { catalogueId } = useParams();
  const [s, setS] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSummary(catalogueId).then(setS).catch((e) => setError(errorMessage(e)));
  }, [catalogueId]);

  if (error) {
    return (
      <div role="alert" className="rounded-md bg-red-50 p-4 text-red-700">
        {error} <Link to="/" className="underline">Upload again</Link>
      </div>
    );
  }
  if (!s) return <p className="text-slate-500">Loading…</p>;

  const types = Object.entries(s.by_type).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...types.map(([, n]) => n));
  const statuses = Object.entries(s.by_status);

  return (
    <div>
      <CatalogueNav catalogueId={catalogueId} />
      <h1 className="mb-4 text-2xl font-semibold">Quality dashboard</h1>

      {s.unmapped_required_fields.length > 0 && (
        <p className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          Required fields not mapped, so their checks were skipped: {s.unmapped_required_fields.join(", ")}.
        </p>
      )}

      <div className="mb-2 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat title="Products" value={s.total_products} />
        <Stat title="Errors" value={s.errors} tone="text-red-600" />
        <Stat title="Warnings" value={s.warnings} tone="text-amber-600" />
        <Stat title="Info" value={s.infos} tone="text-sky-600" />
        <Stat title="Flagged cells" value={s.flagged_cells} />
        <Stat title="Flagged rows" value={s.flagged_rows} />
      </div>
      <p className="mb-2 text-sm">
        <Link to={`/catalogue/${catalogueId}/similar`} className="text-indigo-700 underline">
          Potential duplicates:{" "}
          {s.potential_duplicates == null ? "not checked yet" : s.potential_duplicates}
        </Link>
      </p>
      <p className="mb-6 text-xs text-slate-500">
        Counts show problems still present in the working copy. Rejected and ignored issues are listed below, not hidden.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-lg font-semibold">Open issues by type</h2>
          <ul className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
            {types.map(([t, n]) => (
              <li key={t} className="text-sm">
                <div className="mb-0.5 flex justify-between"><span>{label(t)}</span><span className="font-medium">{n}</span></div>
                <div className="h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-indigo-500" style={{ width: `${(n / max) * 100}%` }} /></div>
              </li>
            ))}
            {types.length === 0 && <li className="text-sm text-slate-500">No open issues.</li>}
          </ul>
        </section>
        <section>
          <h2 className="mb-2 text-lg font-semibold">Review progress</h2>
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {statuses.map(([st, n]) => (
              <li key={st} className="flex justify-between px-4 py-2 text-sm"><span>{label(st)}</span><span className="font-medium">{n}</span></li>
            ))}
            {statuses.length === 0 && <li className="px-4 py-3 text-sm text-slate-500">No issues were found.</li>}
          </ul>
        </section>
      </div>

      <Link
        to={`/catalogue/${catalogueId}/review`}
        className="mt-6 inline-block rounded-md bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700"
      >
        Review catalogue
      </Link>
    </div>
  );
}
