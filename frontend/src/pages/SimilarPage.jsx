import { useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2, Search } from "lucide-react";
import CatalogueNav from "../components/CatalogueNav.jsx";
import { errorMessage, getSimilarProducts, reviewCandidate } from "../services/api.js";

const STATUS_BUTTONS = [
  ["duplicate", "Duplicate"],
  ["not_duplicate", "Not a duplicate"],
  ["needs_investigation", "Needs investigation"],
];

function Score({ title, value }) {
  return (
    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">
      {title} <strong>{value ?? "—"}</strong>
    </span>
  );
}

function CandidateCard({ c, onReview, busy }) {
  const variant = c.relationship === "possible_variant";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${variant ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-800"}`}>
          {variant ? "possible variant" : "possible duplicate"}
        </span>
        <Score title="semantic" value={c.semantic_score?.toFixed(2)} />
        <Score title="name match" value={c.fuzzy_score != null ? `${Math.round(c.fuzzy_score)}` : null} />
        {c.review_status !== "pending" && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">
            {c.review_status.replaceAll("_", " ")}
          </span>
        )}
      </div>
      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        {[["Row", c.source_row_id, c.source_sku, c.source_name], ["Row", c.candidate_row_id, c.candidate_sku, c.candidate_name]].map(([, rid, sku, name]) => (
          <div key={rid} className="rounded-md bg-slate-50 p-3 text-sm">
            <div className="font-medium">{name}</div>
            <div className="text-xs text-slate-500">SKU {sku || "—"} · row {rid + 1}</div>
          </div>
        ))}
      </div>
      <p className="mb-2 text-sm text-slate-700">{c.reason}</p>
      <p className="mb-3 text-xs text-slate-500">
        Matching: {c.matching_fields.join(", ") || "none"}
        {c.differing_fields.length > 0 && <> · Differing: <strong>{c.differing_fields.join(", ")}</strong></>}
      </p>
      <div className="flex flex-wrap gap-2">
        {STATUS_BUTTONS.map(([status, text]) => (
          <button key={status} disabled={busy} onClick={() => onReview(c, status)}
            className={c.review_status === status ? "btn-primary" : "btn"}>
            {text}
          </button>
        ))}
        {c.review_status !== "pending" && (
          <button disabled={busy} onClick={() => onReview(c, "pending")} className="btn">Reset</button>
        )}
      </div>
    </div>
  );
}

export default function SimilarPage() {
  const { catalogueId } = useParams();
  const [semantic, setSemantic] = useState(true);
  const [semThreshold, setSemThreshold] = useState(0.85);
  const [fuzzyThreshold, setFuzzyThreshold] = useState(90);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [show, setShow] = useState("all");

  async function run() {
    setLoading(true);
    setError("");
    try {
      setData(await getSimilarProducts(catalogueId, {
        semantic, semantic_threshold: semThreshold, fuzzy_threshold: fuzzyThreshold,
      }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  async function onReview(c, status) {
    setBusy(true);
    try {
      await reviewCandidate(catalogueId, c.candidate_id, status);
      setData((d) => ({
        ...d,
        candidates: d.candidates.map((x) => (x.candidate_id === c.candidate_id ? { ...x, review_status: status } : x)),
      }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const shown = data?.candidates.filter((c) => show === "all" || c.relationship === show) ?? [];

  return (
    <div>
      <CatalogueNav catalogueId={catalogueId} />
      <h1 className="mb-1 text-2xl font-semibold">Similar products</h1>
      <p className="mb-4 text-sm text-slate-600">
        Candidates for you to review. Similarity does not prove two products are the same, and nothing is merged or changed here.
      </p>

      <div className="mb-4 flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={semantic} onChange={(e) => setSemantic(e.target.checked)} />
          Semantic matching
        </label>
        <label className={semantic ? "" : "opacity-50"}>
          <span className="mb-1 block text-slate-500">Semantic threshold</span>
          <input type="number" min="0" max="1" step="0.01" value={semThreshold} disabled={!semantic}
            onChange={(e) => setSemThreshold(Number(e.target.value))}
            className="w-24 rounded-md border border-slate-300 px-2 py-1" />
        </label>
        <label>
          <span className="mb-1 block text-slate-500">Name-match threshold</span>
          <input type="number" min="0" max="100" step="1" value={fuzzyThreshold}
            onChange={(e) => setFuzzyThreshold(Number(e.target.value))}
            className="w-24 rounded-md border border-slate-300 px-2 py-1" />
        </label>
        <button onClick={run} disabled={loading}
          className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Find similar products
        </button>
      </div>
      {loading && semantic && (
        <p className="mb-3 text-sm text-slate-500">
          The first run downloads and loads the embedding model, which can take a minute.
        </p>
      )}
      {error && <p role="alert" className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {data && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-slate-600">
            <span>{data.candidates.length} candidate pair(s) from {data.compared_rows} products
              {data.skipped_rows > 0 && ` (${data.skipped_rows} without a name were skipped)`}</span>
            <select value={show} onChange={(e) => setShow(e.target.value)} aria-label="Filter candidates"
              className="rounded-md border border-slate-300 px-2 py-1">
              <option value="all">All</option>
              <option value="possible_duplicate">Possible duplicates</option>
              <option value="possible_variant">Possible variants</option>
            </select>
          </div>
          {shown.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500">
              No similar products found at these thresholds.
            </p>
          ) : (
            <div className="space-y-3">
              {shown.map((c) => <CandidateCard key={c.candidate_id} c={c} onReview={onReview} busy={busy} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
