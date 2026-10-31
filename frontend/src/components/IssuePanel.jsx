import { useCallback, useEffect, useState } from "react";
import { Check, EyeOff, Loader2, Pencil, Undo2, X } from "lucide-react";
import { getIssues, errorMessage, reviewIssue, undoIssue } from "../services/api.js";
import { SeverityBadge, StatusBadge, label } from "./Badges.jsx";

const PENDING = ["open", "ready_for_review", "needs_investigation"];
const show = (v) => (v === "" ? <em className="text-slate-400">(empty)</em> : <code className="whitespace-pre-wrap break-all">{JSON.stringify(v)}</code>);

function IssueCard({ issue, busy, onAction }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(issue.current_value);
  const pending = PENDING.includes(issue.status);

  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={issue.severity} />
        <StatusBadge status={issue.status} />
        <span className="text-sm font-medium">{label(issue.issue_type)}</span>
      </div>
      <p className="mb-3 text-sm text-slate-700">{issue.explanation}</p>
      <dl className="mb-3 grid grid-cols-[6rem_1fr] gap-y-1 text-sm">
        <dt className="text-slate-500">Original</dt><dd>{show(issue.original_value)}</dd>
        <dt className="text-slate-500">Current</dt><dd>{show(issue.current_value)}</dd>
        <dt className="text-slate-500">Proposed</dt>
        <dd>{issue.proposed_value == null ? <em className="text-slate-400">none — needs your input</em> : show(issue.proposed_value)}</dd>
      </dl>
      {issue.revalidation_passed === false && (
        <p className="mb-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
          The new value was applied but still fails this check.
        </p>
      )}

      {pending && !editing && (
        <div className="flex flex-wrap gap-2">
          {issue.proposed_value != null && (
            <button disabled={busy} onClick={() => onAction(issue, "accept")} className="btn-primary">
              <Check className="h-4 w-4" /> Accept
            </button>
          )}
          <button disabled={busy} onClick={() => setEditing(true)} className="btn">
            <Pencil className="h-4 w-4" /> Edit
          </button>
          <button disabled={busy} onClick={() => onAction(issue, "reject")} className="btn">
            <X className="h-4 w-4" /> Reject
          </button>
          <button disabled={busy} onClick={() => onAction(issue, "ignore")} className="btn">
            <EyeOff className="h-4 w-4" /> Ignore
          </button>
        </div>
      )}

      {pending && editing && (
        <div className="space-y-2">
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            aria-label="Replacement value"
          />
          <div className="flex gap-2">
            <button
              disabled={busy}
              onClick={async () => { if (await onAction(issue, "edit", value)) setEditing(false); }}
              className="btn-primary"
            >
              Save edit
            </button>
            <button disabled={busy} onClick={() => setEditing(false)} className="btn">Cancel</button>
          </div>
        </div>
      )}

      {!pending && issue.review_action && (
        <button disabled={busy} onClick={() => onAction(issue, "undo")} className="btn">
          <Undo2 className="h-4 w-4" /> Undo {issue.review_action}
        </button>
      )}
    </div>
  );
}

export default function IssuePanel({ catalogueId, rowId, column, onChanged, onClose }) {
  const [issues, setIssues] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getIssues(catalogueId, { row_id: rowId, column });
      setIssues(data.issues);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [catalogueId, rowId, column]);

  useEffect(() => { setIssues(null); load(); }, [load]);

  async function onAction(issue, action, value) {
    setBusy(true);
    setError("");
    try {
      if (action === "undo") await undoIssue(issue.issue_id);
      else await reviewIssue(issue.issue_id, action, value);
      await load();
      onChanged();
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <h2 className="font-semibold">{column}</h2>
          <p className="text-xs text-slate-500">Row {Number(rowId) + 1}</p>
        </div>
        <button onClick={onClose} aria-label="Close panel" className="text-slate-400 hover:text-slate-700">
          <X className="h-5 w-5" />
        </button>
      </div>
      {error && <p role="alert" className="mb-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {!issues && !error && <Loader2 className="h-5 w-5 animate-spin text-slate-400" />}
      <div className="space-y-3">
        {issues?.map((i) => <IssueCard key={`${i.issue_id}-${i.version}`} issue={i} busy={busy} onAction={onAction} />)}
        {issues?.length === 0 && <p className="text-sm text-slate-500">No issues on this cell.</p>}
      </div>
    </aside>
  );
}
