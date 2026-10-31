import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { deleteCatalogue, errorMessage } from "../services/api.js";

const tabs = [
  ["dashboard", "Dashboard"],
  ["review", "Review"],
  ["similar", "Similar products"],
  ["compare", "Comparison & export"],
];

export default function CatalogueNav({ catalogueId }) {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  async function deleteData() {
    if (!window.confirm("Delete this catalogue and all review decisions from the server? Download your files first.")) return;
    try {
      await deleteCatalogue(catalogueId);
      navigate("/");
    } catch (e) {
      // Already expired counts as deleted.
      if (e.response?.status === 404) navigate("/");
      else setError(errorMessage(e));
    }
  }

  return (
    <div className="mb-6">
      <nav className="flex items-center gap-1 border-b border-slate-200">
        {tabs.map(([path, label]) => (
          <NavLink
            key={path}
            to={`/catalogue/${catalogueId}/${path}`}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                isActive ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
        <button onClick={deleteData} className="ml-auto inline-flex items-center gap-1 px-2 py-2 text-xs text-slate-500 hover:text-red-600">
          <Trash2 className="h-3.5 w-3.5" /> Delete my data
        </button>
      </nav>
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    </div>
  );
}
