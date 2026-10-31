// Lets the user map each standard field to one of their CSV columns.
export default function ColumnMapping({ columns, standardFields, requiredFields, mapping, onChange }) {
  const usedBy = Object.fromEntries(Object.entries(mapping).map(([f, c]) => [c, f]));

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {standardFields.map((field) => {
        const required = requiredFields.includes(field);
        const value = mapping[field] || "";
        return (
          <label key={field} className="block text-sm">
            <span className="mb-1 block font-medium">
              {field}
              {required && <span className="text-red-500"> *</span>}
            </span>
            <select
              value={value}
              onChange={(e) => onChange(field, e.target.value)}
              className={`w-full rounded-md border bg-white px-2 py-1.5 ${
                required && !value ? "border-amber-400" : "border-slate-300"
              }`}
            >
              <option value="">— not mapped —</option>
              {columns.map((c) => (
                <option key={c} value={c} disabled={usedBy[c] && usedBy[c] !== field}>
                  {c}
                  {usedBy[c] && usedBy[c] !== field ? ` (used for ${usedBy[c]})` : ""}
                </option>
              ))}
            </select>
          </label>
        );
      })}
    </div>
  );
}
