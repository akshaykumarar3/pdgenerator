# Implementation Plan: Clinical Data Generator Improvements (Task 1)

This plan addresses the 15 requested improvements to the generator engine, ensuring stricter clinical consistency, temporal logic, and formatting across all synthetic patient files.

## Proposed Changes

### 1. PDF Formatting & Tables (`src/doc_generation/pdf_generator.py`)
- **[MODIFY]** Update `create_patient_summary_pdf` and `create_annotator_summary_pdf` table definitions:
  - Add `('WORDWRAP', (0,0), (-1,-1), True)` to all `TableStyle` declarations.
  - Adjust any fixed `colWidths` that cause text clipping or change them to proportional width sizing to ensure no bleeding.

### 2. Provider NPI Consistency & Validation
- **[MODIFY]** `src/doc_generation/validator.py`: Add `validate_npi_consistency(payload: ClinicalDataPayload)` to scan all docs and persona, ensuring 1:1 mapping between NPIs and Provider Names. Throw `ValidationError` if contradictions exist.
- **[MODIFY]** `src/workflow.py` or AI Prompt context: Seed a deterministic mapping of Providers to NPIs so the LLM doesn't hallucinate different NPIs.

### 3. Patient State Schema Extensions (`src/ai/models.py`)
- **[MODIFY]** `PARequestDetails`: Add `units_requested: str = Field(default="1", description="Units Requested for the procedure/authorization")`.
- **[MODIFY]** `StructuredClinicalDoc` / Prompts: Ensure Pre-Op Eval schemas or instructions explicitly request `concurrent_care_reference`.
- **[MODIFY]** `PatientPersona` or Case Config (in `src/core/state.py`): Add a deterministic `has_fit_fobt_result: bool` flag based on case rules.

### 4. AI Prompting & Generation Rules (`src/ai/prompts.py`)
- **[MODIFY]** Add explicit system prompt instructions:
  - **Encounters**: "The encounter list in the clinical summary must be generated *exactly* from the persona master record's encounters."
  - **Labs**: "Lab result events in clinical timelines must map to an existing encounter or be created as a newly documented distinct encounter."
  - **Past Meds**: "Medications with 'past' status must use past tense and appear under 'Previous Treatments' only."
  - **Hold Dates**: "Medication hold instructions must output explicit hold date (procedure date minus hold window), not just duration."
  - **ICD-10 Strictness**: "Every ICD-10 code mentioned anywhere must be present in the supporting diagnoses list."
  - **Comorbidities**: "Relevant comorbidities must be included in the PA risk-benefit section."
  - **Facility Name**: "Procedure facility name must be exactly `{facility_name}` across all headers/consults/schedules. Do not derive independently."
  - **Auth Type Label**: "Use standard auth type label {auth_type_label}. Do not rewrite."
  - **CPT Math**: "CPT codes in therapy plans must precisely match codes in the persona."
  - **Concurrent Care**: "For pre-op eval, if active therapy exists, populate concurrent care reference."
  - **FIT/FOBT**: "Reflect FIT/FOBT result presence exactly as config defines: {fit_fobt_flag}."
  - **Units Requested**: "Always include 'Units Requested' based on procedure type rule."

---

## Verification Plan

### Automated Tests
- Run `TEST_MODE=true python run.py` or `python -m pytest` to test the end-to-end generation for a few cases.
- Confirm `validator.py` accurately catches introduced NPI mismatches in unit tests (I will add a `test_npi_validation()` case to `tests/test_pdf_format.py` or `tests/test_validation.py`).

### Manual Verification
1. Open the generated `Clinical_Summary_Patient_*.pdf` files for a few complex test cases.
2. Verify tables do not crop/bleed text off the margins.
3. Check that the medication hold instructions display a concrete date instead of "hold for X days".
4. Confirm facility name matches identically across PA requests, Consult notes, and the Persona.
5. Search for the NPIs manually in the PDFs and ensure one single provider is linked to each NPI.
