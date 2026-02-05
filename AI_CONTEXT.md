# AI Context: Clinical Data Generator

> **Purpose**: This file provides comprehensive context for AI assistants working on this codebase.

## Product Overview

The Clinical Data Generator is an AI-powered pipeline that synthesizes realistic healthcare data for testing Prior Authorization (PA) workflows. It generates:

- **Clinical PDFs**: Lab reports, consult notes, imaging reports
- **Patient Personas**: FHIR-compliant patient records
- **Clinical Summaries**: Aggregate patient overviews

## Core Architecture

```
generator.py          → Main orchestrator, REPL loop
ai_engine.py          → LLM interaction (OpenAI/Vertex AI)
prompts.py            → Centralized AI prompts & instructions
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
2. User selects generation mode (default: **Persona + Reports + Summary**)
3. System scans for existing documents (smart duplicate prevention)
   - Extracts titles from existing PDFs
   - Passes list to AI to avoid unnecessary duplicates
   - Only generates multiple reports when test case requires it
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

## Recent Changes (Feb 2026)

### Smart Duplicate Detection (NEW)

- **Intelligent Document Scanning**: Scans existing PDFs before generation
- **Title Extraction**: Accurately extracts document titles from filenames
- **Duplicate Prevention**: Prevents creating duplicates like "Doc-221-001 CT scan" and "Doc-221-002 CT scan"
- **Multiple Reports**: Only generates multiple reports when test case specifically requires it
- **AI Integration**: Passes existing document list to AI for smart decision-making

### Updated Default Generation Mode (NEW)

- **New Default**: "Persona + Reports + Summary" (previously "Summary + Reports")
- **Reordered Menu**: More intuitive option ordering
- **Comprehensive Output**: Generates complete patient records by default

### Code Cleanup

- Removed `patch_prompts.py` and `patch_prompts_v2.py` (obsolete patching code)
- Cleaner codebase with better maintainability

### Centralized Prompts

- **`prompts.py`**: All AI instructions now in one file with user-friendly comments
- Helper functions: `get_clinical_data_prompt()`, `get_image_generation_prompt()`, etc.
- Easy customization without touching core logic

### Removed Standalone Image Generation (Feb 2026)

- Removed AI image generation from document workflow
- Documents no longer include standalone generated images
- Simplified generation process focuses on text-based clinical documents

### Windows Compatibility

- Added `run.bat` for Windows users
- Cross-platform documentation in README
- Example configuration files in `cred/examples/`

### Bug Fixes

- Fixed http2 hang in OpenAI client
- Fixed system role error in Vertex AI
- Fixed sequence number duplication

## Common Modification Patterns

### Customize AI Prompts

1. Open `prompts.py` (all prompts centralized here)
2. Edit relevant function or constant
3. Read comments for guidelines
4. Test changes with `TEST_MODE=true`

### Add New Document Type

1. Update `GeneratedDocument` in `ai_engine.py`
2. Add rendering logic in `pdf_generator.py`
3. Update AI prompt in `prompts.py`

### Add New Patient Field

1. Update `PatientPersona` model in `ai_engine.py`
2. Update prompt instructions in `prompts.py`
3. Update PDF rendering in `create_persona_pdf()`

### Change AI Provider

1. Update `LLM_PROVIDER` in `cred/.env`
2. Verify `MODEL_NAME` mapping in `ai_engine.py`

### Improve Image Quality

1. Edit `get_image_generation_prompt()` in `prompts.py`
2. Add specific requirements (resolution, style, anatomical details)
3. Follow comments in prompts.py for guidance

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

**Windows:**

```cmd
:: Syntax check
python -m py_compile generator.py ai_engine.py prompts.py

:: Run with test mode (cheaper/faster)
set TEST_MODE=true
python generator.py
```

**Mac / Linux:**

```bash
# Syntax check
python3 -m py_compile generator.py ai_engine.py prompts.py

# Run with test mode
TEST_MODE=true python3 generator.py
```

## Important Notes for AI

1. All dates use YYYY-MM-DD format
2. Patient IDs are numeric strings (e.g., "210", "237")
3. Document titles should use underscores, not spaces
4. **Smart Duplicate Detection**: Existing documents are scanned and passed to AI to prevent unnecessary duplicates
5. **Multiple Reports**: Only generate multiple reports (e.g., Doc-221-001, Doc-221-002) when test case specifically requires different reports
6. The `generation_mode` dict controls what gets generated (default: all three - persona, reports, summary)
7. **Prompts are in `prompts.py`** - edit there, not in ai_engine.py
8. Default generation mode is now "Persona + Reports + Summary" for comprehensive output
9. **No Standalone Images**: Image generation has been removed from the document workflow
