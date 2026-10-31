export default function PreviewTable({ columns, rows }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">#</th>
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-100">
              <td className="px-3 py-1.5 text-slate-400">{i + 1}</td>
              {columns.map((c) => (
                <td key={c} className="max-w-xs truncate whitespace-pre px-3 py-1.5" title={r[c]}>
                  {r[c]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
