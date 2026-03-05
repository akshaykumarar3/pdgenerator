# AI Context: Clinical Data Generator

> **Purpose**: This file provides comprehensive context for AI assistants working on this codebase.

## Product Overview

The Clinical Data Generator is an AI-powered pipeline that synthesizes realistic healthcare data for testing Prior Authorization (PA) workflows. It generates:

- **Clinical PDFs**: Lab reports, consult notes, imaging reports
- **Patient Personas**: FHIR-compliant patient records
- **Clinical Summaries**: Aggregate patient overviews

## Core Architecture

```text
generator.py          → Main orchestrator, REPL loop
ai_engine.py          → LLM interaction (OpenAI/Vertex AI)
prompts.py            → Centralized AI prompts & instructions
pdf_generator.py      → PDF rendering (ReportLab)
search_engine.py      → 🔍 Web search for medical codes (Tavily API)
doc_validator.py      → Document structure validation
data_loader.py        → Excel case data loading
history_manager.py    → Conversation history
core/patient_db.py    → Patient record persistence
purge_manager.py      → Data cleanup utilities
```

## Key Data Models (ai_engine.py)

- **FacilityDetails**: Healthcare facility information (name, address, city, state, ZIP, department)
- **PARequestDetails**: Prior Authorization request form (provider, urgency, justification, diagnoses, treatments, outcome)
- **PatientPersona**: FHIR-compliant patient with:
  - Demographics, contacts, insurance
  - **NEW**: `expected_procedure_date` (7-90 days future)
  - **NEW**: `procedure_requested` (procedure name)
  - **NEW**: `procedure_facility` (FacilityDetails object)
  - **NEW**: `pa_request` (PARequestDetails object)
- **GeneratedDocument**: Clinical document with title_hint, content, date
- **ClinicalDataPayload**: Combined persona + documents + summary
- **AnnotatorSummary**: Verification guide with case explanation, medical details, verification pointers

## Generation Workflow

1. User enters Patient ID
2. User selects generation mode (default: **Persona + Reports + Summary**)
3. System scans for existing documents (smart duplicate prevention)
   - Extracts titles from existing PDFs
   - Passes list to AI to avoid unnecessary duplicates
   - Only generates multiple reports when test case requires it
4. **Web Search** (if enabled and Excel data incomplete):
   - Checks Excel for procedure/CPT data
   - Searches Tavily API for official CPT/ICD descriptions
   - Adds verification notes for data quality issues
5. AI generates clinical data based on case context + search results
6. Documents are validated; invalid ones get AI repair
7. PDFs are rendered and saved

## Temporal Consistency & PA Workflow

### Future Procedure Dates

All personas include `expected_procedure_date` (7-90 days in future) for realistic Prior Authorization workflows.

**Timeline Requirements**:

- Medical history: 6 months to 5 years BEFORE procedure
- Recent encounters: 1-12 weeks BEFORE procedure
- Lab results: 1-4 weeks BEFORE procedure
- Procedure date: 7-90 days in FUTURE

**Date Calculation Functions** (`generator.py`):

```python
calculate_procedure_date()      # Returns date 7-90 days ahead
calculate_encounter_date(...)   # Calculates relative dates
get_today_date()                # Returns current date
```

### Prior Authorization Request Forms

Each persona includes a complete PA request section with:

- `requesting_provider`: Physician with credentials
- `urgency_level`: Routine/Urgent/Emergency
- `clinical_justification`: Medical necessity (2-3 sentences)
- `supporting_diagnoses`: ICD-10 codes supporting request
- `previous_treatments`: Prior treatments attempted
- `expected_outcome`: Expected clinical benefit

### Facility Location

Realistic healthcare facilities matching patient locality:

- `facility_name`: Hospital/clinic name
- `street_address`, `city`, `state`, `zip_code`: Complete address
- `department`: Appropriate for procedure type
- **Constraint**: Facility MUST be in same state as patient

### Document Coherence

`load_existing_context()` function ensures consistency across generation modes:

- Extracts `procedure_date` and `facility` from existing persona
- Reports/summaries reference same facility and dates
- No contradictory information across documents

## Configuration

**Environment** (`cred/.env`):

- `LLM_PROVIDER`: `openai` or `vertexai`
- `TEST_MODE`: `true` for fast/cheap models
- `OUTPUT_DIR`: Where generated files are saved
- `ENABLE_WEB_SEARCH`: `true` to enable medical code lookup (default: `false`)
- `TAVILY_API_KEY`: API key for web search (get free at <https://tavily.com>)
- `SEARCH_CACHE_TTL`: Cache duration in hours (default: 24)

**Models**:

- Prod: GPT-4o / Gemini 2.5 Pro
- Test: GPT-4o-mini / Gemini 2.5 Flash

## Recent Changes (Feb 2026)

### Web Search Integration (NEW - Feb 15, 2026)

- **Medical Code Lookup**: Retrieves precise CPT/ICD descriptions from authoritative sources (AAPC, CMS)
- **Verification Notes System**: Automatically adds notes when data quality is uncertain
- **Conservative Strategy**: Prioritizes Excel data, only searches when data is missing/incomplete
- **Quality Thresholds**: Rejects poor quality search results (< 20 chars)
- **Caching**: 24-hour file-based cache to reduce API costs
- **Data Models**: `CPTCodeInfo`, `ICD10CodeInfo`, `PolicyCriteria`
- **Configuration**: Optional feature, disabled by default

### Annotator Summary Improvements (NEW - Feb 15, 2026)

- **Simplified PDF Layout**: Removed redundant sections (Target Procedure, Medical Coding Summary table)
- **Clean Table**: Only shows Expected Outcome and Verification Notes
- **Bio Narrative Extraction**: Extracts CPT/ICD codes from patient bio instead of non-existent fields
- **No More N/A**: Removed all "N/A" fallbacks, only shows fields with actual data
- **Embedded Codes**: All CPT/ICD codes now in narrative text for better context

### Smart Duplicate Detection

- **Intelligent Document Scanning**: Scans existing PDFs before generation
- **Title Extraction**: Accurately extracts document titles from filenames
- **Duplicate Prevention**: Prevents creating duplicates like "Doc-221-001 CT scan" and "Doc-221-002 CT scan"
- **Multiple Reports**: Only generates multiple reports when test case specifically requires it
- **AI Integration**: Passes existing document list to AI for smart decision-making

### Updated Default Generation Mode

- **New Default**: "Persona + Reports + Summary" (previously "Summary + Reports")
- **Reordered Menu**: More intuitive option ordering
- **Comprehensive Output**: Generates complete patient records by default

### Code Cleanup

- Removed `patch_prompts.py` and `patch_prompts_v2.py` (obsolete patching code)
- Cleaner codebase with better maintainability

### Phase 9-11 Updates (March 2026)

- **UI Responsive Layout**: Log and Summary panels are alongside each other (side-by-side flex). All UI cards are vertically resizable.
- **Batch Generation (`/api/generate_all`)**: Processes all patients sequentially via the backend instead of triggering 30 parallel frontend requests.
- **Purge Management (`/api/purge`)**: Non-blocking modal in the UI to selectively or entirely wipe Generated Documents, Summaries, Personas, or the entire Patient Database.
- **Save as Template (`/api/template/save`)**: Allows users to save a generated document into the `templates/` folder as a global template, archiving older templates automatically to `templates/archive/`.
- **API Swagger Documentation**: Added `flasgger` to auto-generate OpenAPI spec pages at `/apidocs`.

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
