import { Link, Navigate, Route, Routes } from "react-router-dom";
import { ScanSearch } from "lucide-react";
import UploadPage from "./pages/UploadPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import ComparisonPage from "./pages/ComparisonPage.jsx";
import SimilarPage from "./pages/SimilarPage.jsx";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-6 py-4">
          <ScanSearch className="h-6 w-6 text-indigo-600" />
          <Link to="/" className="text-lg font-semibold">
            CatalogueIQ
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/catalogue/:catalogueId/dashboard" element={<DashboardPage />} />
          <Route path="/catalogue/:catalogueId/review" element={<ReviewPage />} />
          <Route path="/catalogue/:catalogueId/similar" element={<SimilarPage />} />
          <Route path="/catalogue/:catalogueId/compare" element={<ComparisonPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
