# Implementation Plan: Directory Unification & Path Validation

The goal is to ensure that the entire codebase respects the `OUTPUT_DIR` environment variable, specifically for the recent migration to OneDrive storage. We identified hardcoded relative paths in the state management and planning modules that would prevent those assets from moving to the new location.

## User Rationale
- The user moved data to a new path (OneDrive).
- We found that `debug/` state files and `document_plan.json` are currently saved inside the source tree instead of the configured `OUTPUT_DIR`.
- Unifying these ensures that all generated assets (including metadata and debug info) are stored in the custom location.

## Proposed Changes

### 1. Centralized Configuration (`src/core/config.py`)
- Define `DEBUG_DIR = os.path.join(OUTPUT_DIR, "debug")`.
- Add `get_patient_debug_folder(patient_id)` helper.
- Update `ensure_output_dirs` to include `DEBUG_DIR`.

### 2. State & Planner Unification
- **`src/core/state.py`**: Update to use `DEBUG_DIR` and `get_patient_debug_folder` from config.
- **`src/doc_generation/planner.py`**: Update to use `DEBUG_DIR` from config.

### 3. Generator Defaults Cleanup
- **`src/doc_generation/pdf_generator.py`**: Update default arguments to avoid hardcoded relative paths.

### 4. Documentation Update
- Update `ARCHITECTURE.md` and `AI_CONTEXT.md` to confirm the new unified directory structure.

## Verification Plan
1. **Manual Path Check**: Verify that `DEBUG_DIR` resolves correctly to the new OneDrive path when `OUTPUT_DIR` is set.
2. **Success Run**: Run a generation in preview mode and verify that `patient_state_ID.json` appears in the OneDrive folder structure.
3. **Purge Test**: Verify that the purge utility correctly removes files from the new paths.
