const SEVERITY = {
  error: "bg-red-100 text-red-700",
  warning: "bg-amber-100 text-amber-800",
  info: "bg-sky-100 text-sky-700",
};

const STATUS = {
  open: "bg-slate-100 text-slate-700",
  ready_for_review: "bg-indigo-100 text-indigo-700",
  needs_investigation: "bg-orange-100 text-orange-800",
  accepted: "bg-emerald-100 text-emerald-700",
  edited: "bg-emerald-100 text-emerald-700",
  rejected: "bg-slate-200 text-slate-600",
  ignored: "bg-slate-200 text-slate-600",
  resolved: "bg-green-100 text-green-700",
};

const pill = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";
export const label = (s) => s.replaceAll("_", " ");

export const SeverityBadge = ({ severity }) => (
  <span className={`${pill} ${SEVERITY[severity]}`}>{severity}</span>
);

export const StatusBadge = ({ status }) => (
  <span className={`${pill} ${STATUS[status]}`}>{label(status)}</span>
);
