import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Loader2, Search } from "lucide-react";
import CatalogueNav from "../components/CatalogueNav.jsx";
import CatalogueTable, { Legend } from "../components/CatalogueTable.jsx";
import IssuePanel from "../components/IssuePanel.jsx";
import { errorMessage, getCataloguePage } from "../services/api.js";

const PAGE_SIZE = 50;

export default function ReviewPage() {
  const { catalogueId } = useParams();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  // Debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => { setSearch(q); setOffset(0); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { offset, limit: PAGE_SIZE };
      if (search) params.q = search;
      if (severity) params.severity = severity;
      if (flaggedOnly) params.flagged_only = true;
      setPage(await getCataloguePage(catalogueId, params));
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [catalogueId, offset, search, severity, flaggedOnly]);

  useEffect(() => { load(); }, [load]);

  const total = page?.total_rows ?? 0;

  return (
    <div>
      <CatalogueNav catalogueId={catalogueId} />
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2 top-2 h-4 w-4 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search all cells…"
            aria-label="Search"
            className="w-64 rounded-md border border-slate-300 py-1.5 pl-8 pr-2 text-sm"
          />
        </div>
        <select
          value={severity}
          onChange={(e) => { setSeverity(e.target.value); setOffset(0); }}
          aria-label="Severity filter"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">All severities</option>
          <option value="error">Rows with errors</option>
          <option value="warning">Rows with warnings</option>
          <option value="info">Rows with info</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={flaggedOnly} onChange={(e) => { setFlaggedOnly(e.target.checked); setOffset(0); }} />
          Flagged rows only
        </label>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
      </div>
      <div className="mb-3"><Legend /></div>

      {error && <p role="alert" className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <div className={`grid gap-4 ${selected ? "lg:grid-cols-[1fr_22rem]" : ""}`}>
        <div className="min-w-0">
          {page && page.rows.length === 0 && !loading && (
            <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500">
              No products match these filters.
            </p>
          )}
          {page && page.rows.length > 0 && (
            <CatalogueTable page={page} selected={selected} onSelect={setSelected} />
          )}
          {page && total > 0 && (
            <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
              <span>{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total} rows</span>
              <div className="flex gap-2">
                <button className="btn" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}><ChevronLeft className="h-4 w-4" />Prev</button>
                <button className="btn" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next<ChevronRight className="h-4 w-4" /></button>
              </div>
            </div>
          )}
        </div>
        {selected && (
          <IssuePanel
            catalogueId={catalogueId}
            rowId={selected.rowId}
            column={selected.column}
            onChanged={load}
            onClose={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  );
}
