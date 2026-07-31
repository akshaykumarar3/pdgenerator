# AI Context: Clinical Data Generator

## Purpose

This document provides persistent architectural and operational context for AI assistants working on this repository.

Agents must read this file before performing reasoning, planning, or code modifications.

This system generates **synthetic clinical documentation** for testing **Prior Authorization (PA) workflows** in healthcare systems.

Outputs include:

* Clinical reports (lab, imaging, consult notes)
* Patient personas (FHIR-aligned records)
* Clinical summaries for case review
* A concise, bulleted summary with highlighted keywords for quick review
* Verification summaries for annotators
* Policy criteria summaries are intentionally excluded from patient-facing reports and persona outputs

---

# System Overview

The Clinical Data Generator is an **AI-driven pipeline** that synthesizes realistic healthcare documentation from structured case inputs.

Primary responsibilities:

1. Generate realistic patient personas
2. Generate clinical documents aligned with PA workflows (supporting both Approval conditions and Rejection/Denial deficiency cases via `generate_rejection_docs`)
3. Maintain temporal and clinical consistency
4. Prevent document duplication
5. Produce structured outputs for testing automation pipelines

---

# Core Architecture

```text
src/workflow.py              → Main orchestrator and workflow
src/cli.py                   → CLI entrypoint
src/ai/client.py             → LLM interaction layer (OpenAI / Vertex)
src/ai/models.py             → Pydantic data models
src/ai/prompts.py            → Centralized prompt definitions
src/core/state.py            → Deterministic patient identity and demographic state
src/doc_generation/planner.py→ Template planning and document schema selection
src/doc_generation/pdf_generator.py → PDF rendering via ReportLab
src/doc_generation/validator.py     → Validation and formatting of AI-generated documents
src/ai/search_engine.py      → Web search for medical codes (Tavily API)
src/data/loader.py           → Excel test case ingestion
src/data/history.py          → Conversation history
src/core/patient_db.py       → Patient persistence delegator / factory (uses repository abstraction src/core/repository.py, supporting local json [json_repository.py] and postgres [postgres_repository.py] via PATIENT_STORAGE_BACKEND)
src/utils/purge_manager.py   → Cleanup utilities
remove_persona.py            → CLI utility to remove personas

```

Architecture goal:

```text
AI generation
     ↓
Validation
     ↓
Template rendering
     ↓
PDF output
```

This separation ensures reliability and deterministic output structure.

---

# Core Data Models

Defined in `src/ai/models.py`.

### FacilityDetails

Represents healthcare facility metadata.

Fields include:

* facility_name
* street_address
* city
* state
* zip_code
* department

Constraint:

Facility must always match the patient's state.

---

### PARequestDetails

Represents the Prior Authorization request.

Fields include:

* requesting_provider
* urgency_level
* clinical_justification
* supporting_diagnoses
* previous_treatments
* expected_outcome

Purpose:

Provide structured medical justification for requested procedures.

---

### PatientPersona

FHIR-aligned patient model including:

* demographics
* insurance
* contact details
* expected_procedure_date
* procedure_requested
* procedure_facility
* pa_request

New workflow requirement:

Procedure date must be **7–90 days in the future**.

---

### GeneratedDocument

Represents a clinical document.

Fields:

* title_hint
* content (structured dictionary)
* date

Content must always be structured JSON.

---

### ClinicalDataPayload

Combined generation output containing:

* persona
* documents
* summary

---

### AnnotatorSummary

Human verification guide containing:

* case explanation
* verification notes
* clinical reasoning summary

### ConciseSummary

A concise clinical summary structured into 5 parts:
* **Test Case and Overview**: Profile basics + case overview.
* **Details from Extraction**: Insurance details + CPT/ICD/Encounter expectations.
* **Likelihood without Documents**: Baseline PA probability estimation prior to reports.
* **Likelihood PA Score Change**: Impact trajectory when evaluating individual uploaded reports.
* **Overall Summary & Pointers**: Final case summary and verification milestones.

---

# Concurrency & Locking

1. **Parallel Execution**: Multiple threads can run `process_patient_workflow` simultaneously.
2. **Patient Lock**: Only one job per `patient_id` can be active at a time.
3. **Thread-Safe Logging**: Use `ThreadSafeStdout` to map prints to `job_id`.

# Versioning Rules (vMajor.Minor)

1. **Generation involving Persona**: Bumps Major version (`vX.0`).
2. **Generation without Persona**: Bumps Minor version (`vX.n`).
3. **Filenames**: Files must use the version string (e.g., `DOC-225-v3.1-001.pdf`).
4. **Max Major Resolution**: Scan existing files for max integer before incrementing.
5. **Max Minor Resolution**: Scan existing files matching the current Major version for max decimal before incrementing.

---

# Generation Workflow

1. User selects Patient ID
2. User selects generation mode
3. Existing documents are scanned
4. AI receives existing document list
5. AI generates persona and reports
6. Documents are validated
7. Invalid documents are repaired
8. PDFs are rendered and saved

Key rule:

AI must avoid generating duplicate document types when documents already exist.

---

# Temporal Consistency Rules

Procedure timeline must follow:

```text
Medical history → 6 months to 5 years before procedure
Encounters → 1 to 12 weeks before procedure
Lab results → 1 to 4 weeks before procedure
Procedure date → 7 to 90 days in the future
```

Functions in `src/utils/date_utils.py` enforce this:

* calculate_procedure_date()
* calculate_encounter_date()
* get_today_date()

---

# Document Coherence

The function `load_existing_context()` guarantees that:

* procedure date remains consistent
* facility remains consistent
* reports reference the same procedure

Contradictory data across documents must never occur.

**Strict Data Consistency Rules (v5)**:
* **NPI Consistency**: Every provider has EXACTLY one NPI across all encounters, therapies, and documents. No two providers share an NPI.
* **Encounter/Lab Matching**: Encounter lists in summaries perfectly match the persona. Lab events strictly map to existing encounters or create distinct ones.
* **Clinical Coding**: Referenced ICD-10 and CPT codes must identically match codes in the persona profile.
* **Medications**: "Past" medications use past tense and appear strictly under "Previous Treatments" in PA forms. Hold instructions calculate explicit calendar dates.
* **Conditionals**: Pre-Op Eval docs must include Concurrent Care references if active therapies exist. GI cases explicitly flag FIT/FOBT results consistently.
* **PA Fields**: Risk/Benefit justifications explicitly cite comorbidities. Authorization types use standard labels. Units are defaulted or calculated.

Quality guardrails:

* `bio_narrative` is never blank; if the LLM omits it or returns a too-short narrative, it is backfilled from persona data, encounters, diagnoses, and case details.
* Report `past_medical_history` sections are never blank; missing history is backfilled from supporting diagnoses or case context.
* Clinical documents must avoid coverage/appropriateness or sufficiency judgments (e.g., "not indicated", "not medically necessary", "meets criteria", "insufficient evidence"). Notes should remain factual and clinically descriptive.
* When supporting reports are generated, rejection/denial outcomes are converted to approval for clinical document generation. (Annotator summaries may still reflect original test case outcomes.)

---

# Web Search Integration

Optional feature controlled by:

```
ENABLE_WEB_SEARCH=true
```

Uses Tavily API to retrieve:

* CPT descriptions
* ICD-10 descriptions
* policy criteria

Strategy:

1. Prefer Excel case data
2. Use web search only when data is missing
3. Reject poor search results

Cache duration:

```
SEARCH_CACHE_TTL=24 hours
```

---

# V3 Architecture Components

## State Manager

Ensures deterministic patient identity generation.

Prevents AI hallucination of demographics.

---

## Document Planner

Maps case types to template schemas using:

```
templates/document_plan_rules.json
```

Purpose:

Ensure documents follow correct structure before AI generation.

---

## JSON Schema Enforcement

AI must output structured JSON.

`src/doc_generation/validator.py` enforces schema compliance.

Legacy plain text is accepted only as fallback.

---

# Document Content Requirements

All generated clinical documents must be **content-rich**.

Requirements:

* multi-sentence findings
* realistic measurements
* medically plausible details
* structured sections

Sparse documents (<200 characters) should trigger regeneration.

---

# Configuration

Environment variables stored in:

```
cred/.env
```

Externalized rules live in:

```
config/
```

Key settings:

```
LLM_PROVIDER=openai | vertexai
TEST_MODE=true | false
ENABLE_WEB_SEARCH=true | false
OUTPUT_DIR=<path>
```

> **Switching providers**: Only change `LLM_PROVIDER` in `cred/.env`. All credentials for both
> providers are always present in the file. No code changes required.

`GOOGLE_APPLICATION_CREDENTIALS` may be a relative path (e.g. `./cred/gcp_auth_key.json`);
`src/ai/client.py` resolves it against `BASE_DIR` automatically.

Models:

Production:
- GPT-4o (OpenAI)
- Gemini 2.5 Pro (Vertex AI)

Testing:
- GPT-4o-mini (OpenAI)
- Gemini 2.5 Flash (Vertex AI)

---

# Internal Helpers (`src/ai/client.py`)

Shared utilities in `src/ai/client.py`:

```
_strip_json_fences(text)
    → Strips ```json fences from raw model output

_parse_vertex_response(resp, model_class, existing_persona=None)
    → Full Vertex response parser: list unwrap, key alias fix,
      Pydantic validation, and persona recovery fallback

_quantize_prompt(prompt, case_details, patient_state, document_plan,
                 user_feedback, history_context, existing_persona)
    → 3-pass prompt size reducer activated when prompt > 80,000 chars:
      Pass 1 — Trim history_context to first 2000 chars
      Pass 2 — Strip template bodies (keep key names only)
      Pass 3 — Hard truncate at budget boundary
```

Vertex AI `generate_content` calls use `max_output_tokens=65536` in `GenerationConfig`
to prevent JSON truncation on large clinical payloads.

A `vertex_doc_reminder` prefix is prepended to all Vertex AI prompts to force
the `structured_documents` array in responses.

---

# Folder & File Naming Conventions

**Folders (Decoupled Architecture from v5.2)**:
* Active Documents: `generated_output/patient-data/<Patient_ID> - <Patient_Name> - <CPT_Code> - <PA_Outcome>/`
* Metadata tracking: `generated_output/metadata/<Folder_Name>`
* Summary documents: `generated_output/summary/` (Flat structure)
* Generation logs: `generated_output/logs/<Folder_Name>`
* Historical archives: `generated_output/archive/<Folder_Name>`
* Debug & Internal State: `generated_output/debug/`

**Documents**:
```
DOC-{patient_id}-{seq}-{title}.pdf
```

**Persona**:
```
{patient_id}-{name}-persona.pdf
```

**Summary**:
```
Clinical_Summary_Patient_{id}.pdf
```

---

# Maintenance & Utilities

**Compaction Management**:
* `compact_patient_data.py`: Prunes and truncates verbose logs and patient records.
* Logic: Uses section-aware parsing to truncate history and generation feedback while preserving current clinical context.
* Execution: Always run with project venv: `./venv/bin/python3 compact_patient_data.py`.

**Purge Management**:
* Utilities: `src/utils/purge_manager.py` (CLI entrypoints via `run.py`).
* Coverage: Global wipes (`all`, `summaries`, `logs`) and selective patient purging.

---

# Modification Guidelines

## Modify AI Prompts

Edit:

```
src/ai/prompts.py
```

Never modify prompts inside `src/ai/client.py`.

---

## Add Document Type

Steps:

1. Update `GeneratedDocument` model in `src/ai/models.py`
2. Add rendering in `src/doc_generation/pdf_generator.py`
3. Update prompt instructions in `src/ai/prompts.py`

---

## Add Patient Fields

Steps:

1. Update `PatientPersona`
2. Update prompts
3. Update persona PDF rendering

---

# Error Handling

Validation failure:

```
AI repair attempt
```

If repair fails:

```
suffix -NAF
```

AI errors do not terminate generation.

Workflow continues gracefully.

---

# Maintenance & Updates

### v8.7 Code Audit, 404 Route Handling & Bug Fixes (2026-07-29)
* **Dashboard & 404 Route Handling**: Added `@app.route('/')` and `@app.route('/dashboard')` to `api_server.py` to serve the web UI (`ui/index.html`). Implemented custom `@app.errorhandler(404)` returning JSON error objects for `/api/*` requests and a styled Material You dark theme HTML "Page Not Found" page with a prominent "Return to Dashboard" button for HTML page requests. Added client-side routing listener (`handleClientRouting`) in `ui/index.html` for invalid URL hash fragments.
* **Shebang Syntax Fix**: Resolved `SyntaxError` in `compact_patient_data.py` by removing an invalid leading hyphen on line 1 (`-#!/usr/bin/env python3` -> `#!/usr/bin/env python3`).
* **Summary PDF Directory Mapping**: Fixed directory resolution in `api_download_file` and `api_save_template` (`api_server.py`) for `file_type == "summary"` to point to `get_patient_summary_folder(patient_id)` (`generated_output/summary/`).
* **Migration Test Script Refactoring**: Updated `run_migration_test.py` to import `migrate` from `migrate_data` (`direction="json_to_db"` and `direction="db_to_json"`), fixing test collection errors.
* **Pytest Configuration**: Added `pytest.ini` with `pythonpath = .` to ensure automated test suites execute cleanly across developer and CI environments.
* **Robust Unreachable DB Handling**: Wrapped `patient_db.load_patient` in `patient_tracker_export.py` with safe fallbacks and updated `test_tracker.py` / `test_migration.py` to isolate storage backends during unit testing.

### v8.6 Summary PDF Exclusion from Scan Filter (2026-07-23)
* **Summary PDF Exclusion**: Updated workflow processing (`src/workflow.py` and `src/utils/file_utils.py`) to exclude summary documents (`Clinical_Summary_Patient_*.pdf`) from post-processing scan filter rasterization when `scan_mode` (realistic document setting) is enabled. Summary documents remain clean vector PDFs for verification while clinical reports and personas receive scan simulation.

### v8.5 Medicine PA Logic & Document Structure (2026-07-23)
* **Medicine-Specific Data Models**: Extended `PARequestDetails` and `MedicationEntry` in `src/ai/models.py` with 11-digit NDC codes (`ndc_code`), HCPCS drug codes (`hcpcs_code`), administration route, dosing frequency, days supply, refills, and `step_therapy_failed_agents`.
* **Conditional Infusion Order Templates**: Updated `templates/document_plan_rules.json` and `src/doc_generation/planner.py` to route `medication` case types strictly to medicine-specific supporting documents (consult notes, medication history logs, baseline lab reports) and conditionally attach `infusion_order_template.json` only when clinically indicated for provider-administered/infusion drugs.
* **Prompt & Record Output Alignment**: Updated `src/ai/prompts.py` to enforce 11-digit NDC formatting (`XXXXX-XXXX-XX`), step therapy failure rationales, and baseline safety lab findings. Updated `src/data/patient_record_writer.py` to format NDC, HCPCS, route, frequency, and step therapy failure logs in human-readable patient records.
* **Testing Integrity**: Added `tests/test_medicine_logic.py` verifying data models, planner conditional template logic, and patient record text output.

### v8.0 Non-AI Scanned PDF Look & CPT Fixes (2026-06-04)
* **Scan/Non-AI-Friendly Toggle**: Added a post-processing visual scan filter (`src/doc_generation/scan_filter.py`) using fitz (PyMuPDF), Pillow, and NumPy. Converts clean vector PDFs to flat, image-only scanned documents with configurable skews, noise, brightness shadows, and dust/speckle artifacts (Light, Medium, Heavy presets). Fully integrated in `/api/generate`, `/api/generate_from_content`, `/api/generate_all` and the web UI.
* **CPT Code Naming & Low ID Fix**: Resolved the "Unknown" CPT folder naming bug by passing both `CPT Code` and `Code` Excel columns during extraction, and adding fallback resolution to `cpt_code_map.json` by matching procedure names. Lowered patient ID heuristic threshold to `>= 1` to correctly parse low-numeric patient IDs (e.g. 1-99).
* **Likelihood Calibration**: Updated prompts (`src/ai/prompts.py`) to distribute clinical evidence between the Patient Persona and supporting documents for approvals/moderate cases. Ensured that the Patient Persona alone represents a moderate case, and require supporting documents to raise the score. Enforced strict calibrated target likelihood ranges in the concise summary generation instructions.
* **Macro-Gap Injection**: Added a new `Macro-Gap` archetype class (MG-001/MG-002) for denial cases, allowing the system to omit specialist notes or critical diagnostic reports. Updated the selection logic to always include at least one macro-level gap.
* **Medication Prompt Updates**: Added minor adjustments to the medication prompt guidelines to clarify that "procedure" refers to drug administration, explicitly require step-therapy formulary exception details, and pattern medication-specific encounter records (e.g., infusion center visits).

### v8.2 Database Architecture & Cleanup (2026-07-23)
* **Expanded PostgreSQL Schema**: Added DDL tables for `insurance_providers`, `insurance_plans`, and `cpt_code_map` with B-tree and unique indexes (`src/core/schema.sql`).
* **PostgreSQL Repository Methods**: Implemented `load_insurance_config()`, `save_insurance_config()`, `load_cpt_code_map()`, and `save_cpt_code_map()` in `src/core/postgres_repository.py`.
* **Unified Bidirectional Migration**: Created single CLI script `migrate_data.py` supporting bidirectional sync (`json_to_db` and `db_to_json`) for `all`, `patients`, `insurance`, and `cpt` entities with `--strategy update|skip|fail`. Successfully executed migration into PostgreSQL schema `n8n` (73 patients, 5 insurance providers, 14 insurance plans, 27 CPT mappings).
* **DB Error Banner & Health Check**: Updated `/api/status` endpoint in `api_server.py` to test active database connection. Added animated red top ribbon error banner (`#db-error-banner`) and DB status indicator dot (`#db-dot`) in `ui/index.html` to alert the user of connection errors, timeouts, or authentication failures.
* **Redundant Code & UI Cleanup**: Removed legacy `src/doc_generation/patient_tracker_export.py`, `@app.route("/api/patient_tracker_export")`, `@app.route("/api/purge")`, and associated HTML/JS elements for Batch Purge and Tracker Export in `ui/index.html`.
* **UI Event Listener & Syntax Cleanup**: Resolved `ui/index.html` initialization script crashes by removing the event listener for the deleted `batch-purge-modal` and removing dangling/duplicated tracker export and purge functions.
* **Database Connection Error Fallback**: Added exception handling to `/api/patients` in `api_server.py` to fall back gracefully to a default name pattern (`Patient {id}`) when database connections fail, ensuring patient listing is not blocked.
* **Bulk Patient Name Lookup (v8.2.1 fix)**: Replaced N sequential `get_patient_name()` DB calls in `/api/patients` with a single `get_patient_names_bulk()` call. Added `get_patient_names_bulk(patient_ids)` method to `PatientRepository` base class, `PostgresPatientRepository` (uses `WHERE patient_id = ANY(%s)` — one query), and `JSONPatientRepository`. Exposed via `patient_db.get_patient_names_bulk()`. This fixes the patient dropdown stalling on page load when the PostgreSQL backend has high latency or connection errors, reducing 77 DB round-trips to 1.

### v8.3 Instant Patient Roster & UI Loaders (2026-07-23)
* **Local Name Cache** (`src/core/name_cache.py`): New thread-safe module that persists `{patient_id: display_name}` to `core/patient_name_cache.json`. `load_cache()` returns instantly from disk; `save_cache()` and `update_entry()` are mutex-protected to prevent race conditions from background threads.
* **Cache-First `/api/patients`**: The endpoint now reads IDs from Excel and names from the local cache (total ~50 ms, no DB), then spawns a daemon thread to refresh names from PostgreSQL/JSON in the background. Next page load shows real generated names automatically.
* **Live Cache Writes in Workflow**: `src/workflow.py` imports `name_cache` and calls `name_cache.update_entry(patient_id, name)` immediately after both `patient_db.save_patient()` calls so the dropdown shows the correct name as soon as a persona is generated — without waiting for the background refresh cycle.
* **UI — Page Loader**: Full-screen white overlay (`#page-loader`) with spinning indicator and "Loading patient roster…" label. Fades out (CSS transition) once `loadPatients()` resolves — success or failure.
* **UI — Patient Selector Spinner**: Small inline spinner next to the "Active Patient" label (`#patient-select-spinner`) that shows while `/api/patients` is in flight. Shows a clear ⚠ error message in the dropdown if the server is unreachable.
* **UI — Clinical Skeleton**: Shimmer skeleton lines (`#clinical-loading`) appear inside the clinical content pane while `/api/patient/<id>` is fetching. All content children are hidden during the load, then restored once data arrives.
* **UI — Doc List Skeleton**: Three skeleton shimmer bars replace the document list while `/api/output/<id>` is in flight (called by `showDocSkeleton()` from `onPatientChange()`).
* **Improved Error Surface**: `loadPatients()` now checks `r.ok` and `d.error` before populating the dropdown, and logs a descriptive console error with the function name prefix for easier browser DevTools debugging.

### v7.0 Prior Authorization Tracker CSV Export Transition (2026-05-22)
* **High-Fidelity CSV Exporter**: Replaced the ReportLab landscape PDF and companion TSV with a single, premium standard CSV file (`patient_tracker_export.csv`) located directly inside `generated_output/patient-data/`.
* **HTML Sanitization**: Ensured all cells in the exported CSV are completely sanitized of HTML tags, using standard newlines (`\n`) and plain text bullets (`- `) to ensure compatibility with Microsoft Excel copy-pasting.
* **Excel CSV Safety / Formula Injection Protection**: Implemented sanitization logic inside `patient_tracker_export.py` to prevent Excel CSV formula injection. Automatically prepends a single quote (`'`) to any cell value that starts with formula triggers (`=`, `+`, `@`).
* **API Server Integration**: Updated the `/api/patient_tracker_export` endpoint to serve the generated CSV with `download_name="patient_tracker_export.csv"` and `mimetype="text/csv"`.
* **Testing Integrity**: Updated the unit test suite in `tests/test_tracker.py` to assert CSV schema compliance, checking exactly 12 columns.

### v6.0 Clinical Prior Authorization Pipeline Enhancements (2026-05-22)
* **Limit Supporting Documents to Max 5**: Added `MAX_SUPPORTING_DOCUMENTS = 5` settings and capped document selects across planner, workflow, and API previews. Ensured that capping applies *only* to supporting documents (e.g. consult notes, imaging reports) while always keeping core documents (Prior Authorization Requests and Summaries) fully intact. Included feedback-driven override to bypass capping when explicit commands are supplied in user comments.
* **Medications Target Support**: Treated medications as first-class PA targets. Integrated regex check `^[JQjq]\d{4}$` in `planner.py` to route HCPC drug codes (e.g. `J0897`, `Q5124`) straight to `medication` case types instead of diagnostic. Expanded loader (`loader.py`) and state manager (`state.py`) to correctly ingest both 5-digit CPT codes and J/Q HCPC medication codes. Expanded prompts to incorporate medication-specific guidelines (indication, step-therapy, labs, failed therapies). Implemented dynamic HCPC vs CPT prefix shifts in the exporter, and upgraded clinical PDF compiler regexes to support J/Q medicine codes.
* **Notification Removal**: Completely removed all browser notification permission requests and calls to `showNotification(...)` in the UI to present a clean, uninterrupted user experience.
* **Patient Tracker Export Schema & Integrity**: Upgraded `patient_tracker_export.py` module to generate a 12-column table. The 12 columns are: Patient ID, Patient Name, Department, CPT/HCPC Code, Procedure/Medicine Name, Provider, Insurance Type, Policy Name, extraction expectation (corresponds to details_from_extraction), likelihood expectations (corresponds to likelihood_without_documents), attachments, and post-attachment likelihood.
* **Payer & Provider Extraction Correction**: Reads insurer details under the `payer` block of generated personas (with fallback to `insurance`) and extracts separate Provider and Policy Name fields into individual columns.
* **Persona PDF Exclusions**: Excludes all version-suffixed persona PDFs case-insensitively checking for `"persona"` in filenames during attachment scanning.


### v5.3 Gap Injection System Overhaul (2026-04-09)
* **Multi-Dimensional Gap Archetypes**: Added `GAP_ARCHETYPE_POOL` in `src/ai/prompts.py` — 20 archetypes across 5 clinical dimensions (Profile-Behavior, Temporal-Sequence, Treatment-Escalation, Cross-Document, Policy-Criteria).
* **Weighted Selector**: `_select_gap_archetypes()` randomizes 2–4 archetypes per run, guaranteeing ≥2 distinct dimensions and ≥1 high-impact (TE or PC) archetype per denial case.
* **Sophisticated Gap Builder**: `get_rejection_gap_instruction()` produces a self-contained prompt block with per-archetype injection instructions and mandatory anti-pattern guards.
* **Approval/Denial Dispatch**: `_build_clinical_logic_instruction()` replaces the old single-line blunt directive — approval cases get strong-evidence instructions; denial cases get the gap injection protocol.
* **Anti-Pattern Guards**: Explicitly prohibit blank sections, `[MISSING]` labels, single-obvious-value errors, and gap concentration in one document.
* **Design Goal**: Gaps are detectable only by cross-referencing ≥2 data dimensions; no gap is visible from a single document read-through.

### v5.2 Directory Restructuring (2026-04-08)
* **Decoupled Architecture**: `logs/`, `metadata/`, `archive/`, and `debug/` data have been entirely moved out of the `patient-data/` folder and decoupled to reside top-level inside `generated_output/`.
* **Dynamic Folder Naming**: Patient folders dynamically append `CPT Code` and `PA Outcome` attributes (e.g. `101 - Sandor - 12345 - PA Approval`). 
* **Granular Archiving**: Document overrides automatically and specifically archive (rather than delete) older PDFs (i.e. replacing *only* personas vs all files) during new generation loops into `generated_output/archive/...`

### v4.1 Robustness Improvements (2026-04-07)
* **Indentation Fix**: Resolved `IndentationError` in `src/workflow.py` causing server startup failures.
* **Folder Safety**: Added `patient_report_folder` validation and fallback logic to prevent `os.makedirs` crashes during headless generation or persona name alignment.
* **API Stability**: Corrected `history_manager` local import in `api_server.py` to use `src.data.history`.
* **Dependency Alignment**: Added `Flask` and `Flask-Cors` to `requirements.txt`.

---

# Testing

Mac/Linux

```
python3 -m py_compile src/ai/client.py src/ai/prompts.py src/cli.py
TEST_MODE=true python3 run.py
```

Windows

```
python -m py_compile src/ai/client.py src/ai/prompts.py src/cli.py
set TEST_MODE=true
python run.py
```

---

# UI

The interface file is in `ui/index.html` (Material You dark theme), which implements the **3-silo layout**:

**3-Silo Layout:**

| Silo | Content |
|------|---------|
| Left (280px) | Patient selector + UAT case info (test case #, dept, CPT, expected outcome) + identity dossier |
| Center (flex) | 7 inline clinical tabs: Medications / Allergies / Therapy / Procedures / Encounters / Imaging / Labs |
| Right (300px) | Generation controls (feedback, doc type checkboxes, generate button) + live log stream + doc list |

**Batch Modal:** Header button opens modal with all-patient checklist → `POST /api/generate_all`.

**API endpoints used:**

- `GET /api/patients` — patient ID list for selector
- `GET /api/patient/<id>` — identity + case_details (UAT info) + clinical history
- `GET /api/output/<id>` — list of generated documents
- `GET /api/download/<id>/<type>/<name>` — open PDF inline
- `POST /api/generate` — spawn single-patient generation job
- `POST /api/generate_all` — spawn batch generation job
- `GET /api/job/<job_id>?since=<offset>` — poll job status + incremental logs

**Log Streaming Pattern:**
- The job poll endpoint returns `{ status, logs: [...], log_total, ... }` — the field is `logs`, NOT `new_logs`
- The UI tracks a `logOffset` variable (reset to 0 on each new job start)
- Each poll request includes `?since=${logOffset}` so only new log lines are returned
- After receiving logs, the UI increments `logOffset += d.logs.length`
- This prevents duplicate log entries on successive polls

API server runs on `http://localhost:410` by default (`API_PORT` env var).

---

# Database Persistence & Migrations

The patient storage persistence layer uses a repository pattern decoupled from business logic:
- Toggle between backends using `PATIENT_STORAGE_BACKEND` env var: `'json'` (local file) or `'postgres'` (PostgreSQL database).
- **PostgreSQL Schema**: Defined in `src/core/schema.sql`. Schema is initialized automatically via the repository (exactly once per instance via `_schema_initialized` guard). Uses indices on `last_name, first_name` and `dob` for deduplication/listing, and a GIN index on `persona_data` (JSONB) for robust querying.
- **Migration Scripts**:
  - `migrate_data.py` is the unified bidirectional migration CLI tool (supporting `json_to_db` and `db_to_json`) for `all`, `patients`, `insurance`, and `cpt` entities.
  - Accepts `--strategy` option (`skip`, `update`, `fail`) to resolve duplicate ID conflicts.
- **Strict Backend Selection**: Storage operations strictly execute on the configured `PATIENT_STORAGE_BACKEND` (`'json'` or `'postgres'`). No silent cross-backend fallback occurs: if PostgreSQL is unreachable in `'postgres'` mode, explicit database errors (HTTP 500) are returned. Complete feature parity is maintained in both `'json'` and `'postgres'` modes.
- **Schema name validation**: `DB_SCHEMA` env var is validated against `^[a-zA-Z_][a-zA-Z0-9_]*$` on repository instantiation.
- **All patient data operations** route through `src/core/patient_db.py` → `PatientRepository` → active backend. No module touches `patients_db.json` directly outside `json_repository.py`.

---

# Post-Audit Fixes Applied (2026-07-21)

Full audit report: `artifacts/audit_report.md`

Fixes applied:
- `compact_patient_data.py`: Fixed `NameError` crash on `--all` — replaced `set(data.keys())` with `set(patient_db.list_patient_ids())`.
- `compact_patient_data.py`: Removed dead `_compact_patient_db()` function (legacy direct-JSON code, no longer called).
- `src/utils/purge_manager.py`: Removed unused `DB_PATH = patient_db.DB_PATH` import.
- `src/core/postgres_repository.py`: Added `_schema_initialized` guard — DDL runs once per instance, not per operation.
- `src/core/postgres_repository.py`: Added `DB_SCHEMA` name regex validation in `__init__`.
- `cred/.env.example`: Added missing `API_PORT` variable.
- `README.md`: Fixed three references pointing to `core/.env.example` → `cred/.env.example`.

---

# Production Readiness & Final Polish (2026-07-21)

Applied final polish updates:
- `run.py`: Created root-level CLI launcher script for bootstrapping the interactive interface.
- `src/remove_persona.py`: Fixed `purge_manager` import path to prevent CLI execution failures.
- `tests/test_repository.py`: Added SQL injection and schema validation unit tests.
- Deletions: Removed obsolete empty `patients_db.json` (root) and legacy `core/.env.example`.

---

# Key Rules for AI Agents

1. Dates must use `MM-DD-YYYY`
2. Patient IDs are numeric strings
3. Document titles must use underscores
4. Avoid generating duplicate reports
5. Prompts must only be edited in `src/ai/prompts.py`
6. All documents must be internally consistent
7. Do NOT add parsing logic inline — use `_parse_vertex_response()`
8. Do NOT call `client.client.start_chat()` — use `generate_content()` directly
9. All Vertex AI calls must include `max_output_tokens=65536`
10. Call `_quantize_prompt()` before sending large prompts to Vertex AI
