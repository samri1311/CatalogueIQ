# CatalogueIQ demo script (about 7 minutes)

## Before you start

1. Start the backend (`uvicorn app.main:app --port 8000` from `backend/`) and the frontend (`npm run dev` from `frontend/`).
2. Open http://localhost:5173.
3. Warm up the embedding model once so the demo does not pause: open the Similar products tab on any catalogue and run it
   (about 30 s the first time; it needs internet only for the very first download).

Sample files are in `backend/sample_data/`:
- `synthetic_catalogue.csv`: 10 products with deliberate problems and an unknown column (`warehouse_note`).
- `similarity_catalogue.csv`: 21 products with labelled duplicates, variants and look-alikes.

## 1. Upload and mapping (1 min)

- Drag `synthetic_catalogue.csv` onto the page. Point out the preview and that `warehouse_note` is kept.
- Show the suggested column mapping; change one if you like. Click **Run quality checks**.

## 2. Dashboard (30 s)

- Errors, warnings, info, flagged cells. Note "Potential duplicates: not checked yet".

## 3. Review and correct (2.5 min)

- Open **Review**. Explain the colours (red error, amber warning, blue info).
- Search "bottle", or tick *Flagged rows only*.
- Click the whitespace cell in row 6: it proposes the trimmed name. **Accept**. It turns resolved.
- Click the price `-500` in row 4: error, **no proposed value** ("we won't guess"). **Edit** it to `-3` and show it is
  applied but *still failing*; then **Undo** and edit it to `59.90` to resolve it.
- Click `tshirts` (row 3): **Reject** the suggestion; the cell stays as uploaded.
- Click the `10.0` stock cell: **Ignore**.

## 4. Similar products (1 min)

- Upload `similarity_catalogue.csv`, run checks, open **Similar products**, click **Find similar products**.
- Show a possible duplicate (T-Shirt vs Tshirt) and a possible variant (Running Shoes, size 42 vs 43).
- Say it plainly: similarity suggests candidates; nothing is merged. Mark one *Duplicate* and one *Not a duplicate*.
- Mention: raising the semantic threshold to 0.95 or lowering it to 0.70 changes precision; defaults were chosen from
  measured scores (`python -m scripts.evaluate_similarity`).

## 5. Compare and export (1.5 min)

- Open **Comparison & export** on the first catalogue. Show original vs corrected values.
- Read the summary aloud: some issues are unresolved and one is ignored, so the page says the catalogue is *not fully clean*.
- Download the cleaned CSV and the quality report and open them. Show that column order and `warehouse_note` are
  unchanged, rejected/ignored values are untouched, and each report row has a decision and status.
- Optional: upload a CSV containing `=1+1` in a cell and show it exported as `'=1+1`.

## 6. Close (30 s)

- Click **Delete my data**. Say what is and is not stored: in memory only, expires after 2 hours, large uploads are
  briefly spooled to a temp file and deleted, no authentication, runs locally.

## If something goes wrong

- *Similar products shows a model error:* you are offline on the first run. Untick **Semantic matching** to run
  name-matching only.
- *"Catalogue not found or expired":* the backend restarted (sessions are in memory). Upload again.
