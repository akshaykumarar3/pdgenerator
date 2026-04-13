# Plan: Batch Fix + Cancel + Offline + Preview Repair

## Key Changes
1. **Batch selection correctness**
   - Configure `/Users/akshaykumar/code/lucenz/pdgenerator/api_server.py`'s `api_generate_all()` to strictly enforce `patient_ids` and pass to `_run_batch_generation()`. Iterate exactly in order and log skipped/invalid IDs.

2. **Cancellation (backend + workflow)**
   - Add `POST /api/cancel/<job_id>` in `api_server.py`.
   - Pass `cancel_check` param into `/Users/akshaykumar/code/lucenz/pdgenerator/src/workflow.py` methods and break execution early at safe boundaries if tripped.

3. **Rollback / restore on cancel (delete partial outputs)**
   - Introduce `archive_token` in `archive_patient_files()` inside `src/utils/file_utils.py` to silo archives.
   - Implement `restore_patient_files()` to undo partial outputs on cancellation.
   - Invoke restoration from `api_server.py` upon job cancellation.

4. **Preview checkbox + primary Generate (both UIs)**
   - Standardize generation trigger to a single "Generate" button dependent on a "Preview before generating" checkbox in `index.html` and `index2.html`.

5. **Preview modal fix (full document + pagination)**
   - Overhaul the preview presentation to use a hidden measurement DOM element, slicing content sequentially into multiple generated `.a4-page` elements.
   - Trigger repagination dynamically on Quill `text-change` and during initial rendering.

6. **Offline mode (both UIs)**
   - Expand `checkServer()` into generalized `setOnlineState(isOnline)` to disable interactive components transparently and summon an API Offline banner with a Refresh capability.
