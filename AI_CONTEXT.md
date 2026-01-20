# AI Context: Clinical Data Generator

> **Purpose**: This file provides comprehensive context for AI assistants working on this codebase.

## Product Overview

The Clinical Data Generator is an AI-powered pipeline that synthesizes realistic healthcare data for testing Prior Authorization (PA) workflows. It generates:

- **Clinical PDFs**: Lab reports, consult notes, imaging reports
- **Medical Images**: AI-generated MRI/CT scans
- **Patient Personas**: FHIR-compliant patient records
- **Clinical Summaries**: Aggregate patient overviews

## Core Architecture

```
generator.py          → Main orchestrator, REPL loop
ai_engine.py          → LLM interaction (OpenAI/Vertex AI)
pdf_generator.py      → PDF rendering (ReportLab)
doc_validator.py      → Document structure validation
data_loader.py        → Excel case data loading
history_manager.py    → Conversation history
core/patient_db.py    → Patient record persistence
purge_manager.py      → Data cleanup utilities
```

## Key Data Models (ai_engine.py)

- **PatientPersona**: FHIR-compliant patient with demographics, contacts, insurance
- **GeneratedDocument**: Clinical document with title_hint, content, date
- **ClinicalDataPayload**: Combined persona + documents + summary

## Generation Workflow

1. User enters Patient ID
2. User selects generation mode (Summary/Reports/Persona/All)
3. System scans for existing documents (duplicate prevention)
4. AI generates clinical data based on case context
5. Documents are validated; invalid ones get AI repair
6. PDFs are rendered and saved

## Configuration

**Environment** (`cred/.env`):

- `LLM_PROVIDER`: `openai` or `vertexai`
- `TEST_MODE`: `true` for fast/cheap models
- `OUTPUT_DIR`: Where generated files are saved

**Models**:

- Prod: GPT-4o / Gemini 2.5 Pro
- Test: GPT-4o-mini / Gemini 2.5 Flash

## Recent Changes (Jan 2026)

### Document Generation Enhancements

- **Interactive Mode Selection**: Menu for Summary/Reports/Persona/All
- **Smart Duplicate Prevention**: Scans existing titles, passes to AI
- **Summary Template**: `templates/summary_template.json`

### Refactoring

- Removed SQL generation logic
- Added AI-friendly validation with retry loop
- Extracted helpers: document scanning, generation loops

### Bug Fixes

- Fixed http2 hang in OpenAI client
- Fixed system role error in Vertex AI
- Fixed sequence number duplication

## Common Modification Patterns

### Add New Document Type

1. Update `GeneratedDocument` in `ai_engine.py`
2. Add rendering logic in `pdf_generator.py`
3. Update AI prompt to include new type

### Add New Patient Field

1. Update `PatientPersona` model in `ai_engine.py`
2. Update prompt instructions
3. Update PDF rendering in `create_persona_pdf()`

### Change AI Provider

1. Update `LLM_PROVIDER` in `cred/.env`
2. Verify `MODEL_NAME` mapping in `ai_engine.py`

## File Naming Conventions

- Documents: `DOC-{patient_id}-{seq}-{title}.pdf`
- Personas: `{patient_id}-{name}-persona.pdf`
- Summaries: `Clinical_Summary_Patient_{id}.pdf`
- Images: `{title}_{timestamp}.png`

## Error Handling

- **Validation Failure**: AI attempts repair; suffix `-NAF` if repair fails
- **AI Failure**: Exception caught, error printed, workflow continues
- **Missing Data**: Graceful fallbacks with default values

## Testing

```bash
# Syntax check
python3 -m py_compile generator.py ai_engine.py

# Run with test mode (cheaper/faster)
TEST_MODE=true python3 generator.py
```

## Important Notes for AI

1. All dates use YYYY-MM-DD format
2. Patient IDs are numeric strings (e.g., "210", "237")
3. Document titles should use underscores, not spaces
4. Existing documents inform AI to avoid duplicates
5. The `generation_mode` dict controls what gets generated
