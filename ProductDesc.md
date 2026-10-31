# Master Development Prompt: CatalogueIQ

## 1. Your Role

Act as a senior full-stack engineer, Python backend architect, React developer, and applied AI engineer.

Help me build **CatalogueIQ**, a product catalogue quality analysis and correction platform. Work directly with my existing project files if available. Write production-minded, maintainable code suitable for a demonstrable MVP.

Do not merely explain what I should build. Help me implement it, file by file, with runnable code, tests, and clear instructions.

I am building this project on a CPU-only laptop, so the solution must be practical on modest hardware.

## 2. Product Objective

CatalogueIQ allows users to upload a product catalogue CSV, detect quality problems, inspect proposed corrections, approve or reject changes, compare original and corrected data, and export a cleaned catalogue.

The product should combine:
- Deterministic data-quality validation.
- Text normalization and fuzzy matching.
- Semantic similarity using local embeddings.
- A human-in-the-loop review workflow.
- Safe CSV export.

The application must never silently overwrite original data or automatically apply unapproved AI suggestions.

## 3. Technology Stack

### Backend
- Python 3.11
- FastAPI
- Uvicorn
- Pandas
- NumPy
- Pydantic
- Python-multipart
- RapidFuzz
- Sentence Transformers
- scikit-learn
- Pytest
- HTTPX

Use the dependencies defined in my existing `requirements.txt` if present. Do not arbitrarily upgrade or replace working dependencies.

### Frontend
- React
- Vite
- JavaScript
- Tailwind CSS
- Axios
- React Router
- Lucide React

Use TanStack Table only if it provides a meaningful benefit for the catalogue table.

### Embedding Model
Use the pretrained model:

`sentence-transformers/all-MiniLM-L6-v2`

This model should run locally on the CPU. It must not require a paid API, API key, GPU, or Llama installation.

The first model download requires internet access. Subsequent inference should use the locally cached model.

### Storage
For the initial MVP:
- Do not require PostgreSQL, Supabase, or a vector database.
- Process catalogues using temporary session data.
- Keep the original dataset separate from the working copy.
- Store embeddings in memory unless persistent projects are explicitly introduced later.
- Do not add user authentication yet.

Design interfaces so persistent storage can be introduced later without rewriting the entire application.

## 4. Catalogue Input

Support CSV files with these recommended fields:

- sku
- product_name
- description
- category
- brand
- price
- currency
- color
- material
- size
- stock_quantity
- product_url
- image_url

The SKU, product name, category, and price fields are important for the standard template, but the application must handle optional fields and custom catalogues.

Implement a column-mapping step that lets users map arbitrary CSV headers to standard fields.

Preserve:
- Original column names.
- Original column order.
- Row order.
- Original cell values.
- Original values for comparison and undo.

Do not silently discard unrecognized columns.

## 5. Core Product Workflow

Implement this complete workflow:

1. Upload a CSV file.
2. Validate the file and preview its contents.
3. Map CSV columns to standard fields when necessary.
4. Run deterministic quality checks.
5. Display a quality dashboard.
6. Display a searchable, filterable product table.
7. Highlight cells with quality issues.
8. Show an issue explanation and suggested action when a user selects a flagged cell.
9. Allow users to accept, edit, reject, or ignore suggestions.
10. Revalidate edited or accepted values.
11. Allow supported changes to be undone.
12. Display original versus corrected values.
13. Export a cleaned CSV.
14. Export a separate quality report.

The original dataset must remain unchanged throughout this process.

## 6. Phase One: Deterministic Quality Engine

Implement these checks first:

- Missing required values.
- Duplicate SKUs.
- Negative prices.
- Invalid numeric values.
- Negative stock quantities.
- Malformed URLs.
- Leading and trailing whitespace.
- Inconsistent formatting.
- Known category or attribute mapping inconsistencies.
- Missing or invalid currency values where applicable.

Use clear severity levels:
- Error: a confirmed validation failure.
- Warning: a potential issue requiring judgment.
- Info: a non-critical observation.

Do not invent replacement values for unknown facts.

For example, if a product price is -500, flag it as invalid. Do not guess that the correct price is 500.

Use deterministic corrections only when the intended result is clear, such as trimming whitespace.

## 7. Issue Ledger and Review System

Create a structured issue model using Pydantic.

Each issue should support fields such as:
- issue_id
- row_id
- sku
- column
- original_value
- current_value
- issue_type
- severity
- explanation
- proposed_value, when justified
- status
- review_action
- timestamps or version information where appropriate

Issue statuses should include:
- open
- ready_for_review
- needs_investigation
- accepted
- edited
- rejected
- ignored
- resolved

Keep the original value, proposed value, and current working value conceptually separate.

Review actions:
- Accept: apply the approved proposal to the working copy.
- Edit: allow the user to enter a replacement value.
- Reject: do not apply the suggestion.
- Ignore: retain the value and mark the issue as intentionally ignored.
- Undo: revert a supported change to its previous working value.

After a change, rerun the relevant validation rules. A cell should not become valid merely because a suggestion was accepted.

## 8. Phase Two: Intelligence Layer

Build the intelligence layer only after the basic upload, validation, review, and export workflow works.

Keep intelligence components separate from API routes and frontend code.

### A. RapidFuzz

Use RapidFuzz to detect:
- Nearly identical product titles.
- Spelling variations.
- Minor punctuation or formatting differences.
- Similar product names that deserve investigation.

Do not treat fuzzy similarity alone as proof that two products are duplicates.

### B. Sentence Transformers

Use `sentence-transformers/all-MiniLM-L6-v2` to generate embeddings for product text.

Create an `embedding_service.py` module responsible for:
- Loading the model once rather than on every request.
- Preparing product text from relevant fields.
- Generating normalized embeddings.
- Reusing embeddings within a temporary catalogue session when possible.
- Handling empty or missing descriptions.
- Reporting useful errors if the model cannot load.

For an initial implementation, combine product name, category, brand, and description carefully. Avoid adding irrelevant or missing values as literal text.

### C. Semantic Similarity

Use scikit-learn or NumPy to calculate cosine similarity between product embeddings.

Initially:
- Compare products within the uploaded catalogue.
- Rank the closest candidates.
- Exclude a product from matching itself.
- Avoid unnecessary comparisons when the catalogue is small.
- Make similarity thresholds configurable.
- Display candidate products and their scores for review.
- Do not automatically merge products.

A high semantic similarity score does not prove duplication. Two products may share similar descriptions but differ in SKU, size, color, brand, or other important attributes.

### D. Intelligence Output

Return structured candidate results containing:
- Source product identifier.
- Candidate product identifier.
- Similarity score.
- Matching fields.
- Reason for flagging.
- Review status.

Use deterministic rules to validate hard constraints. Embedding similarity should help retrieve candidates, not determine whether a product is definitively wrong.

### E. Optional LLM Integration

Do not implement an LLM API in the initial version.

Keep the architecture extensible so an LLM can later suggest product title improvements, identify contextual inconsistencies, or extract explicitly stated attributes.

If introduced later:
- Make it optional.
- Never let it directly mutate catalogue data.
- Validate structured output.
- Require user review before applying changes.
- Do not invent product facts.
- Send only the relevant fields needed for a task.

## 9. Backend Architecture

Use a clean structure similar to:

backend/
- app/
  - main.py
  - api/
    - upload.py
    - analysis.py
    - review.py
    - export.py
  - models/
    - issue.py
  - services/
    - csv_loader.py
    - normalizer.py
    - quality_engine.py
    - issue_manager.py
    - export_service.py
  - intelligence/
    - embedding_service.py
    - fuzzy_matcher.py
    - duplicate_detector.py
  - tests/
- requirements.txt

You may adjust the structure if there is a clear engineering reason. Do not create unnecessary abstractions or empty modules without purpose.

## 10. API Endpoints

Implement a small and consistent API.

Suggested endpoints:

- POST `/api/upload`
- GET `/api/catalogue/{catalogue_id}`
- POST `/api/catalogue/{catalogue_id}/analyze`
- GET `/api/catalogue/{catalogue_id}/issues`
- GET `/api/catalogue/{catalogue_id}/similar-products`
- POST `/api/issues/{issue_id}/review`
- POST `/api/issues/{issue_id}/undo`
- GET `/api/catalogue/{catalogue_id}/comparison`
- GET `/api/catalogue/{catalogue_id}/export`
- GET `/api/catalogue/{catalogue_id}/report`
- GET `/health`

These are initial proposals. You can simplify the API where necessary, but keep the design coherent.

Define request and response schemas with Pydantic. Return clear HTTP status codes and helpful error messages.

Configure CORS appropriately for the local React development server.

## 11. Frontend Requirements

Build a clean, professional SaaS interface.

### Page 1: Upload
- Drag-and-drop CSV upload.
- File validation.
- Upload progress or processing state.
- Preview of imported rows.
- Column mapping.

### Page 2: Quality Dashboard
- Total product count.
- Errors, warnings, and information items.
- Flagged cell count.
- Issue breakdown by type.
- Potential duplicate count.
- Navigation to the detailed catalogue.

### Page 3: Catalogue Review
- Searchable and filterable product table.
- Cell-level issue indicators.
- Different visual states for errors, warnings, valid cells, and unchecked cells.
- Issue detail panel.
- Original value and proposed value.
- Accept, edit, reject, ignore, and undo actions.
- Clear loading, empty, and error states.

### Page 4: Comparison and Export
- Original versus corrected values.
- Approved changes.
- Unresolved issues.
- Download cleaned CSV.
- Download quality report.

Use React components rather than placing the entire application inside one component.

Create an API service module to centralize Axios calls. Do not put all API requests directly into UI components.

Keep the frontend and backend independently runnable.

## 12. Export Requirements

The cleaned CSV must:
- Preserve original column names.
- Preserve original column order.
- Preserve row order.
- Retain unknown columns.
- Apply only approved or user-entered changes.
- Never apply rejected suggestions.
- Handle null and empty values consistently.
- Guard against CSV formula injection for values that spreadsheet applications might interpret as formulas.

The quality report should include:
- Issue ID.
- Row identifier or SKU.
- Column.
- Issue type.
- Severity.
- Original value.
- Final value.
- Review decision.
- Resolution status.

Do not claim that every issue is resolved if some were ignored or left open.

## 13. Privacy and Security

CatalogueIQ should be temporary-processing-first.

Implement:
- File-size and row-count limits.
- File type validation.
- Safe parsing and clear errors for malformed CSVs.
- No unnecessary logging of catalogue contents.
- Cleanup of temporary files and session data.
- No permanent storage of uploaded catalogues by default.
- No permanent storage of embeddings by default.
- No public exposure of uploaded files.
- Appropriate CORS settings.
- Safe CSV exports.

Be precise about temporary storage. Framework upload handling may spool larger uploads to disk. Verify the actual behavior and cleanup rather than assuming every uploaded file stays in memory.

Do not add claims such as "zero data retention" unless the implementation genuinely guarantees them.

## 14. Testing Requirements

Write tests alongside implementation.

Backend tests should cover:
- CSV parsing.
- Column mapping.
- Missing and malformed values.
- Duplicate SKU detection.
- Price and stock validation.
- Review actions.
- Revalidation after edits.
- Undo behavior.
- Original-data preservation.
- Similarity candidate generation.
- Export integrity.
- Temporary-data cleanup.

Use a synthetic catalogue containing:
- Exact duplicate products.
- Similar products with different wording.
- Products with different sizes or colors.
- Unrelated products.
- Invalid prices.
- Missing fields.
- Duplicate SKUs.
- Unknown columns.

For semantic search, create labelled examples of likely matches and non-matches. Evaluate actual results rather than assuming a particular similarity score is always correct.

## 15. Four-Week Roadmap

### Week 1: Foundation
- Set up project structure.
- Create the backend environment.
- Set up FastAPI and React.
- Create test catalogues.
- Implement CSV upload, preview, and column mapping.
- Implement the first deterministic validation rules.

### Week 2: Review Workflow
- Build the dashboard and catalogue table.
- Implement the issue ledger.
- Add review actions.
- Implement working-copy updates and revalidation.
- Implement before-and-after values.
- Test data preservation and undo.

### Week 3: Intelligence
- Load the Sentence Transformers model locally.
- Implement embedding generation.
- Implement cosine similarity.
- Add RapidFuzz matching.
- Build duplicate candidate review.
- Evaluate the results against labelled test data.

### Week 4: Export and Demo
- Implement cleaned CSV export.
- Implement quality report export.
- Complete privacy and security checks.
- Add error handling.
- Run end-to-end tests.
- Polish the interface.
- Prepare a complete demonstration.

If time is limited, prioritize a reliable end-to-end workflow over advanced intelligence features.

## 16. Engineering Rules

Follow these rules throughout development:

1. Do not implement the entire application in one enormous file.
2. Do not generate all modules with placeholder code and claim the project is complete.
3. Do not add a vector database, Supabase, authentication, or an LLM API unless there is a demonstrated requirement.
4. Do not load the embedding model repeatedly for every product or API request.
5. Do not let AI suggestions automatically alter the original dataset.
6. Do not silently discard columns or rows.
7. Do not assume that similar product descriptions indicate duplicates.
8. Do not hard-code similarity thresholds without making them configurable.
9. Do not suppress errors that would hide data corruption.
10. Do not make unrelated changes to working code.
11. Do not invent successful test results.
12. Keep configuration in appropriate settings or environment variables.
13. Write useful tests for important behavior.
14. Explain the purpose of each significant module.
15. Keep the code understandable and maintainable for a solo developer.

## 17. How We Will Work Together

Work incrementally.

**First, inspect the current project.**

If a repository or files are available:
- Inspect the existing structure.
- Read the current dependency files.
- Identify what already works.
- Identify missing components.
- Avoid overwriting working code without a reason.

If no project exists:
- Propose the initial directory structure.
- Provide exact terminal commands to create it.

Then create an implementation plan with:
- Files to create or modify.
- Purpose of each file.
- API contracts.
- Dependencies.
- Tests required.
- Definition of done.

After the plan, begin with **Phase 1, Week 1**.

For each implementation step:
1. State the objective.
2. Create or modify the required files.
3. Provide complete, runnable code.
4. Explain how to install and run it.
5. Execute available tests when tool access permits.
6. Report actual results, including failures.
7. Fix issues before moving on.
8. Keep track of completed work and the next task.

Do not jump to semantic search before the CSV upload and validation workflow is working.

If you encounter an ambiguity, make a reasonable engineering choice and state the assumption unless the decision would materially change the architecture.

## 18. Definition of Done

The MVP is complete when a user can:

1. Upload a product catalogue CSV.
2. Preview the data and map columns.
3. Identify real data-quality issues.
4. Review and correct selected values.
5. Find semantically similar product candidates.
6. Accept, edit, reject, ignore, and undo supported changes.
7. Compare original and corrected values.
8. Export a cleaned CSV.
9. Export a quality report.
10. Complete the workflow without the original uploaded data being silently overwritten.

The application must run locally on Python 3.11 and a CPU-only laptop, without requiring paid APIs or persistent database infrastructure.

**Start now by inspecting my existing project or helping me create the initial project structure. Do not skip ahead to later phases.**