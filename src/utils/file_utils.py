import os
import re
import shutil

from ..core.config import PERSONA_DIR, SUMMARY_DIR, get_patient_report_folder

def get_persona_version(patient_id: str) -> int:
    """
    Scan the persona directory for existing files for this patient.
    Returns the *next* version number (e.g. if v2 exists → returns 3).
    Returns 1 when no prior versions exist.
    """
    max_v = 0
    prefix = f"{patient_id}-"
    if os.path.isdir(PERSONA_DIR):
        for fname in os.listdir(PERSONA_DIR):
            if fname.startswith(prefix) and fname.endswith(".pdf"):
                m = re.search(r"-v(\\d+)", fname)
                if m:
                    max_v = max(max_v, int(m.group(1)))
    return max_v + 1


def _archive_files_in_dir(folder: str, patient_id: str, match_all_pdfs: bool = False):
    """
    Move PDFs belonging to *patient_id* from *folder* into folder/archive/.
    If match_all_pdfs is True every .pdf in the folder is archived (used for
    the patient-specific reports sub-folder which already only contains that
    patient's files).
    """
    if not os.path.isdir(folder):
        return

    archive_dir = os.path.join(folder, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    prefix_patterns = [
        f"{patient_id}-",
        f"DOC-{patient_id}-",
        f"Clinical_Summary_Patient_{patient_id}",
    ]

    moved = 0
    for fname in os.listdir(folder):
        if fname == "archive" or not fname.endswith(".pdf"):
            continue
        if match_all_pdfs or any(fname.startswith(p) for p in prefix_patterns):
            src = os.path.join(folder, fname)
            dst = os.path.join(archive_dir, fname)
            try:
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                print(f"      ⚠️  Archive move failed for {fname}: {e}")

    if moved:
        print(f"      📦 Archived {moved} file(s) from {os.path.basename(folder)}/")


def archive_patient_files(patient_id: str, generation_mode: dict):
    """
    Archive existing patient documents for every doc type that will be
    re-generated in this run.  Only files about to be overwritten are moved.

    Args:
        patient_id:       Patient ID string.
        generation_mode:  Dict with boolean flags 'persona', 'reports', 'summary'.
    """
    if generation_mode.get("persona", False):
        _archive_files_in_dir(PERSONA_DIR, patient_id)

    if generation_mode.get("summary", False):
        _archive_files_in_dir(SUMMARY_DIR, patient_id)

    if generation_mode.get("reports", False):
        # Reports live in a patient-specific sub-folder; archive everything there
        rpt_folder = get_patient_report_folder(patient_id)
        _archive_files_in_dir(rpt_folder, patient_id, match_all_pdfs=True)


def sanitize_filename_component(name: str) -> str:
    """Make a safe filename segment across OSes."""
    if not name:
        return "document"
    name = name.replace(os.sep, "-").replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]+', "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name
