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
src/core/patient_db.py       → Patient persistence (data: src/core/patients_db.json; auto-migrates legacy core/patients_db.json)
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

Two interface files in `ui/` — both implement the **3-silo layout**:

| File | Theme | Description |
|------|-------|-------------|
| `index.html` | Dark (Material You) | Material dark design |
| `index2.html` | Light (Command Center) | Clean light design |

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
