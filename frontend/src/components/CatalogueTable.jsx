// Cell colours: red/amber/blue = open issue by severity, dashed = rejected/ignored,
// green = resolved, white = checked and valid, grey = column has no rules (unmapped).
function cellClass(cell, checked) {
  if (cell?.state === "open") {
    return {
      error: "bg-red-100 ring-1 ring-inset ring-red-300",
      warning: "bg-amber-100 ring-1 ring-inset ring-amber-300",
      info: "bg-sky-100 ring-1 ring-inset ring-sky-300",
    }[cell.severity];
  }
  if (cell?.state === "dismissed") return "bg-white ring-1 ring-inset ring-slate-400 ring-dashed";
  if (cell?.state === "resolved") return "bg-green-50 ring-1 ring-inset ring-green-300";
  return checked ? "bg-white" : "bg-slate-50 text-slate-500";
}

export default function CatalogueTable({ page, selected, onSelect }) {
  const checked = new Set(page.checked_columns);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full border-collapse text-sm">
        <thead className="bg-slate-100 text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">Row</th>
            {page.columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {page.rows.map((row) => {
            const rid = row.__row_id__;
            return (
              <tr key={rid} className="border-t border-slate-100">
                <td className="px-3 py-1.5 text-slate-400">{Number(rid) + 1}</td>
                {page.columns.map((col) => {
                  const cell = page.cells[rid]?.[col];
                  const isSel = selected?.rowId === rid && selected?.column === col;
                  return (
                    <td
                      key={col}
                      onClick={() => cell && onSelect({ rowId: rid, column: col })}
                      title={row[col]}
                      className={`max-w-[14rem] truncate whitespace-pre px-3 py-1.5 ${cellClass(cell, checked.has(col))} ${
                        cell ? "cursor-pointer hover:brightness-95" : ""
                      } ${isSel ? "outline outline-2 outline-indigo-600" : ""}`}
                    >
                      {row[col]}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Legend() {
  const items = [
    ["bg-red-100 ring-red-300", "Error"],
    ["bg-amber-100 ring-amber-300", "Warning"],
    ["bg-sky-100 ring-sky-300", "Info"],
    ["bg-white ring-slate-400 ring-dashed", "Rejected / ignored"],
    ["bg-green-50 ring-green-300", "Resolved"],
    ["bg-white ring-slate-200", "Valid"],
    ["bg-slate-50 ring-slate-200", "Unchecked column"],
  ];
  return (
    <div className="flex flex-wrap gap-3 text-xs text-slate-600">
      {items.map(([cls, text]) => (
        <span key={text} className="inline-flex items-center gap-1">
          <span className={`inline-block h-3 w-3 rounded-sm ring-1 ring-inset ${cls}`} />
          {text}
        </span>
      ))}
    </div>
  );
}
