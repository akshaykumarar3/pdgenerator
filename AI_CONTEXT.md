# AI Context: Clinical Data Generator

## Purpose

This document provides persistent architectural and operational context for AI assistants working on this repository.

Agents must read this file before performing reasoning, planning, or code modifications.

This system generates **synthetic clinical documentation** for testing **Prior Authorization (PA) workflows** in healthcare systems.

Outputs include:

* Clinical reports (lab, imaging, consult notes)
* Patient personas (FHIR-aligned records)
* Clinical summaries for case review
* Verification summaries for annotators

---

# System Overview

The Clinical Data Generator is an **AI-driven pipeline** that synthesizes realistic healthcare documentation from structured case inputs.

Primary responsibilities:

1. Generate realistic patient personas
2. Generate clinical documents aligned with PA workflows
3. Maintain temporal and clinical consistency
4. Prevent document duplication
5. Produce structured outputs for testing automation pipelines

---

# Core Architecture

```text
generator.py          → Main orchestrator and REPL workflow
ai_engine.py          → LLM interaction layer (OpenAI / Vertex)
prompts.py            → Centralized prompt definitions
state_manager.py      → Deterministic patient identity and demographic state
document_planner.py   → Template planning and document schema selection
pdf_generator.py      → PDF rendering via ReportLab
doc_validator.py      → Validation and formatting of AI-generated documents
search_engine.py      → Web search for medical codes (Tavily API)
data_loader.py        → Excel test case ingestion
history_manager.py    → Conversation history
core/patient_db.py    → Patient persistence
purge_manager.py      → Cleanup utilities
remove_persona.py     → CLI utility to remove personas
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

Defined in `ai_engine.py`.

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

Functions in `generator.py` enforce this:

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

`doc_validator.py` enforces schema compliance.

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

Key settings:

```
LLM_PROVIDER=openai | vertexai
TEST_MODE=true | false
ENABLE_WEB_SEARCH=true | false
OUTPUT_DIR=<path>
```

Models:

Production:
- GPT-4o
- Gemini 2.5 Pro (via vertexai with explicit GenerativeModel imports)

Testing:
- GPT-4o-mini
- Gemini 2.5 Flash

---

# File Naming Conventions

Documents

```
DOC-{patient_id}-{seq}-{title}.pdf
```

Persona

```
{patient_id}-{name}-persona.pdf
```

Summary

```
Clinical_Summary_Patient_{id}.pdf
```

---

# Modification Guidelines

## Modify AI Prompts

Edit:

```
prompts.py
```

Never modify prompts inside `ai_engine.py`.

---

## Add Document Type

Steps:

1. Update `GeneratedDocument` model
2. Add rendering in `pdf_generator.py`
3. Update prompt instructions

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

# Testing

Mac/Linux

```
python3 -m py_compile generator.py ai_engine.py prompts.py
TEST_MODE=true python3 generator.py
```

Windows

```
python -m py_compile generator.py ai_engine.py prompts.py
set TEST_MODE=true
python generator.py
```

---

# Key Rules for AI Agents

1. Dates must use `YYYY-MM-DD`
2. Patient IDs are numeric strings
3. Document titles must use underscores
4. Avoid generating duplicate reports
5. Generation mode controls output scope
6. Prompts must only be edited in `prompts.py`
7. All documents must be internally consistent