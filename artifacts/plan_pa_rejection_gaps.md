# Implementation Plan: PA Rejection Gaps

## 1. Objective
Modify the clinical document generation logic so that when a case represents a Prior Authorization (PA) rejection, the system generates documents with intentional gaps (e.g., missing critical tests, ambiguous findings, or failing to meet criteria). The user should be able to explicitly define these gaps, falling back to default critical gaps if none are provided.

## 2. API Server Updates (`api_server.py`)
- **Endpoints**: Update `POST /api/generate` and `POST /api/preview` to accept two new variables from the request body:
  - `generate_rejection_docs` (boolean): Flag to bypass the forced positive outcome and explicitly configure a rejection scenario.
  - `rejection_gaps` (string): User-provided specific gaps (e.g., "Missing MRI report, no conservative treatment noted").
- **Worker Logic**: Update the `_run_generation` and `_run_preview_generation` methods to pass these variables down to the `workflow.py` functions natively. Provide the logic to append these specific gaps to the AI `feedback` string. 
  - If `generate_rejection_docs` is True:
    - If `rejection_gaps` is provided, add `[REJECTION GAPS / DENIAL FOCUS]: ...` into the extra feedback block.
    - If no `rejection_gaps` are provided, add default instructions: `[REJECTION GAPS / DENIAL FOCUS]: Ensure the clinical evidence is insufficient. Omit critical supportive findings, exclude documentation of prior conservative treatments, and ensure the criteria for PA approval are explicitly NOT met.`

## 3. Workflow Orchestrator (`src/workflow.py`)
- **Bypass Positive Forcing**: `_force_positive_outcome` currently overwrites any rejection outcome with "PA Approval" whenever reports are being generated. 
  - Update `process_patient_workflow()` and `preview_patient_generation()` to check if `generate_rejection_docs` is True.
  - If True, bypass the call to `_force_positive_outcome()` and retain the original "Denial" or "Rejection" target outcome, passing it straight to the AI engine.

## 4. Prompt Logic (`src/ai/prompts.py`)
- The prompt already handles `<Denial>` outcomes (e.g. `If Target is Denial/Low Probability -> REMOVE supporting evidence or make findings ambiguous/normal.`). Together with the injected `feedback` explicitly instructing the AI on what gaps to synthesize, the AI will build the required scenario.

## 5. UI Updates (`ui/index.html` & `ui/index2.html`)
- **Generation Controls Panel**: Add a new toggle/checkbox: `[x] Generate Rejection / Denial Gaps`.
- **Gaps Input**: Add a text input or textarea (`Specific missing criteria / gaps`) that appears when the checkbox is checked, allowing the user to type in specific gaps.
- **Auto-check**: In the Javascript where case details are fetched (`GET /api/patient/<id>`), auto-check the toggle if the `case_details.outcome` contains words like "Denial" or "Rejection".
- **Payload update**: Include `generate_rejection_docs` and `rejection_gaps` in the JSON body when sending POST `/api/generate` or `/api/preview`.

## 6. Execution Tasks
- [ ] Update `src/workflow.py` to support `generate_rejection_docs` parameter.
- [ ] Update `api_server.py` endpoints and background threads to parse new properties and append instructions to `feedback`.
- [ ] Add the checkbox and input fields to `ui/index.html`.
- [ ] Add the checkbox and input fields to `ui/index2.html`.
- [ ] Update `README.md` and `AI_CONTEXT.md` to document the new Rejection Generation capabilities.

## 7. Persona PDF Tabular Wrap Fix (`src/doc_generation/pdf_generator.py`)
- **Issue**: ReportLab `Table` doesn't automatically wrap plain string content in cells, causing tabular data in `create_persona_pdf` (like Identity, Contact, Social History, Vital Signs, PA fields) to crop or spill over.
- **Fix**: Wrap all table cell string constants and variables in `Paragraph(str(value), style)` before passing them to the `Table` class.
- **Execution Task**: Parse all arrays (e.g., `data_identity`, `data_communication`, `data_contact`, `data_provider`, `data_payer`, `sh_data`, `vs_data`, `pa_data`, headers for medications/allergies/therapies) and apply `Paragraph` styling to ensure `WORDWRAP` works properly without breaking the existing bold fonts applied via `TableStyle`.
