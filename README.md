# CatalogueIQ

See [ProductDesc.md](ProductDesc.md) for the full spec.

## Run the backend (Python 3.11)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m pytest -q
```

`sentence-transformers` pulls in PyTorch, which is large. On a CPU-only machine install the CPU build first to avoid
the multi-GB CUDA download:

```powershell
.\.venv\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

The first similarity run downloads `all-MiniLM-L6-v2` (internet needed) and takes about 30 s to load; later runs use the
local cache. Evaluate matching quality on the labelled sample catalogue with
`.\.venv\Scripts\python.exe -m scripts.evaluate_similarity`.

## Run the frontend

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173, talks to http://localhost:8000
```

Settings (env vars): `CATALOGUEIQ_MAX_UPLOAD_BYTES`, `CATALOGUEIQ_MAX_ROWS`, `CATALOGUEIQ_MAX_COLUMNS`,
`CATALOGUEIQ_SESSION_TTL_SECONDS`, `CATALOGUEIQ_CORS_ORIGINS`, and `VITE_API_URL` for the frontend.

## Review workflow (Week 2)

- `POST /api/issues/{id}/review` (`accept`, `edit`, `reject`, `ignore`) and `POST /api/issues/{id}/undo`.
- Only the working copy changes. After every action the whole working copy is revalidated, so an
  accepted or edited value is marked `resolved` only if the problem is really gone.
- Undo is newest-first per cell. Re-running `analyze` restarts the review and discards decisions.
- Revalidation re-runs every rule (about 1.2 s at the 50,000-row limit).

## Similar products (Week 3)

- `GET /api/catalogue/{id}/similar-products` ranks candidate pairs using embeddings (cosine similarity) and RapidFuzz
  name matching, then labels each pair a possible duplicate or possible variant using fixed attribute rules.
  Thresholds are query parameters; defaults come from `CATALOGUEIQ_SEMANTIC_THRESHOLD` (0.85) and
  `CATALOGUEIQ_FUZZY_THRESHOLD` (90). `semantic=false` runs name matching only (works offline).
- Candidates are suggestions. Nothing is merged or changed; your judgement is stored per pair in memory.
- Measured on the 21-product labelled sample: true pairs scored >= 0.96, similar-but-different products 0.70-0.81,
  unrelated <= 0.42. That sample is small, so tune the threshold on your own data.
- Known limit: two different products with the same brand and attributes (a mouse and a keyboard from one brand)
  look like a "possible duplicate" if their text is similar enough. Only a person can rule that out.
- Capped at 5,000 products (`CATALOGUEIQ_MAX_SIMILARITY_ROWS`) because every product is compared with every other.

## Export (Week 4)

- `GET /api/catalogue/{id}/export` returns the cleaned CSV: original column names and order, row order, unknown columns,
  and only the changes you accepted or typed. Rejected and ignored suggestions never appear in it.
- `GET /api/catalogue/{id}/report` returns one row per issue: issue id, file line, SKU, column, type, severity,
  original value, final value, review decision, and resolution status (`resolved`, `unresolved`,
  `applied_but_still_failing`, `rejected_left_as_is`, `ignored_left_as_is`). Nothing is described as fixed unless
  revalidation confirms it.
- Formula-injection guard: any cell starting with `=`, `+`, `-` or `@` (or a tab/CR) that is not a plain number gets a
  leading apostrophe, in both files. Plain numbers such as `-500` are left alone. This does change those cells'
  text, so a value like `=1+1` in your own data is exported as `'=1+1`.
- Files are UTF-8 with a BOM (so Excel shows accents correctly) and CRLF line endings. Empty cells are empty strings.

## Privacy and security, as actually implemented

- **Storage:** catalogues, working copies, embeddings and review decisions live only in process memory. No database,
  no persistent files. Sessions expire after `CATALOGUEIQ_SESSION_TTL_SECONDS` (default 2 h, swept every minute), the
  least recently used session is evicted beyond `CATALOGUEIQ_MAX_SESSIONS` (20), the "Delete my data" button calls
  `DELETE /api/catalogue/{id}`, and everything is cleared when the server stops.
- **Upload temp files (measured):** uploads up to about 1 MB stay in memory. Larger uploads are spooled by Starlette
  to a temporary file while the request is read, and that file is removed when the handler closes it. A test confirms
  a 1.9 MB upload leaves nothing behind in the system temp folder. Because of this spooling, this is not a
  "memory only" guarantee for large files.
- **Limits:** 10 MB request body (rejected early, including chunked bodies, before parsing), 50,000 rows, 100 columns,
  `.csv` only, binary content rejected, malformed rows rejected with the line number.
- **Logging:** the app writes no catalogue values to logs (a test checks this). Uvicorn's access log records request
  URLs only. An unexpected crash traceback is not something the app can fully control, so do not paste logs
  publicly without checking them.
- **HTTP:** CORS allows only `CATALOGUEIQ_CORS_ORIGINS` (the Vite dev server by default); API responses are
  `Cache-Control: no-store`; `X-Content-Type-Options: nosniff`.
- **Not provided:** there is no authentication and no encryption in transit (it is meant to run locally). Do not
  expose the backend to a network as-is. This is a local, temporary-processing tool, not a "zero data retention"
  service.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

115 tests cover CSV parsing and limits, mapping, every quality rule, review actions, revalidation, undo, original-data
preservation, similarity (with a fake encoder, plus real-model evaluation that skips if the model is unavailable), export
integrity, formula injection, temp-file cleanup, log privacy, and a full upload-to-export workflow.

See [DEMO.md](DEMO.md) for a walkthrough script.
