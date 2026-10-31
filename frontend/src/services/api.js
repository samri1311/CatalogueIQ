// All HTTP calls live here so components never use Axios directly.
import axios from "axios";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

export function errorMessage(err) {
  if (err.response?.data?.detail) {
    const d = err.response.data.detail;
    return typeof d === "string" ? d : JSON.stringify(d);
  }
  if (err.code === "ERR_NETWORK") return "Cannot reach the CatalogueIQ server. Is the backend running?";
  return err.message || "Something went wrong.";
}

export async function uploadCatalogue(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post("/api/upload", form, {
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  });
  return data;
}

export async function getCataloguePage(id, params = {}) {
  const { data } = await http.get(`/api/catalogue/${id}`, { params });
  return data;
}

export async function analyzeCatalogue(id, mapping) {
  const { data } = await http.post(`/api/catalogue/${id}/analyze`, { mapping });
  return data;
}

export async function getIssues(id, filters = {}) {
  const { data } = await http.get(`/api/catalogue/${id}/issues`, { params: filters });
  return data;
}

export async function deleteCatalogue(id) {
  await http.delete(`/api/catalogue/${id}`);
}

export async function getSummary(id) {
  const { data } = await http.get(`/api/catalogue/${id}/summary`);
  return data;
}

export async function reviewIssue(issueId, action, value) {
  const { data } = await http.post(`/api/issues/${issueId}/review`, { action, value });
  return data;
}

export async function undoIssue(issueId) {
  const { data } = await http.post(`/api/issues/${issueId}/undo`);
  return data;
}

export async function getComparison(id) {
  const { data } = await http.get(`/api/catalogue/${id}/comparison`);
  return data;
}

export async function getSimilarProducts(id, params = {}) {
  // First semantic run may download the embedding model, so allow a long wait.
  const { data } = await http.get(`/api/catalogue/${id}/similar-products`, { params, timeout: 600000 });
  return data;
}

export async function reviewCandidate(id, candidateId, status) {
  const { data } = await http.post(`/api/catalogue/${id}/similar-products/${candidateId}/review`, { status });
  return data;
}

// Downloads "export" (cleaned CSV) or "report" (quality report) and saves it in the browser.
export async function downloadCsv(id, kind) {
  const res = await http.get(`/api/catalogue/${id}/${kind}`, { responseType: "blob" });
  const match = /filename="([^"]+)"/.exec(res.headers["content-disposition"] || "");
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = match ? match[1] : `${kind}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
