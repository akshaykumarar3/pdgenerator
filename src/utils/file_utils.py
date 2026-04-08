import os
import re
import shutil

import datetime

from ..core.config import (
    get_patient_report_folder,
    get_patient_logs_folder,
    get_patient_archive_folder,
)

def get_persona_version(patient_id: str) -> int:
    """
    Scan the document directories for existing files for this patient.
    Uses os.walk to check active AND archived folders to find the absolute max version.
    Returns the *next* version number (e.g. if v2 exists → returns 3).
    Returns 1 when no prior versions exist.
    """
    max_v = 0
    
    prefix_patterns = [
        f"{patient_id}-",
        f"DOC-{patient_id}-",
        f"Clinical_Summary_Patient_{patient_id}",
    ]
    
    dirs_to_check = [get_patient_report_folder(patient_id)]
    
    for d in dirs_to_check:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for fname in files:
                    if fname.endswith(".pdf") and any(fname.startswith(p) for p in prefix_patterns):
                        m = re.search(r"-v(\d+)", fname)
                        if m:
                            max_v = max(max_v, int(m.group(1)))
                            
    return max_v + 1


def _archive_files_in_dir(folder: str, patient_id: str, prefix_patterns: list[str], archive_token: str = None):
    """
    Move PDFs matching prefix patterns into the patient's archive/log folder.
    """
    if not os.path.isdir(folder):
        return

    archive_dir = get_patient_archive_folder(patient_id)
    os.makedirs(archive_dir, exist_ok=True)
    token_prefix = f"{archive_token}__" if archive_token else f"archived_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}__"

    moved = 0
    for fname in os.listdir(folder):
        if fname == "archive" or not fname.endswith(".pdf"):
            continue
        if any(fname.startswith(p) for p in prefix_patterns):
            src = os.path.join(folder, fname)
            dst = os.path.join(archive_dir, f"{token_prefix}{fname}")
            try:
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                print(f"      ⚠️  Archive move failed for {fname}: {e}")

    if moved:
        print(f"      📦 Archived {moved} file(s) from {os.path.basename(folder)}/")


def archive_patient_files(patient_id: str, generation_mode: dict, archive_token: str = None):
    """
    Archive existing patient documents for every doc type that will be
    re-generated in this run.  Only files about to be overwritten are moved.

    Args:
        patient_id:       Patient ID string.
        generation_mode:  Dict with boolean flags 'persona', 'reports', 'summary'.
    """
    prefix_patterns = []
    if generation_mode.get("persona", False):
        prefix_patterns.append(f"{patient_id}-")
    if generation_mode.get("reports", False):
        prefix_patterns.append(f"DOC-{patient_id}-")
    if generation_mode.get("summary", False):
        prefix_patterns.append(f"Clinical_Summary_Patient_{patient_id}")

    if prefix_patterns:
        root_folder = get_patient_report_folder(patient_id)
        _archive_files_in_dir(root_folder, patient_id, prefix_patterns, archive_token=archive_token)

def restore_patient_files(patient_id: str, generation_mode: dict, archive_token: str):
    """Restore files from archive/<archive_token> and delete current outputs."""
    if not archive_token:
        return

    folder = get_patient_report_folder(patient_id)
    if not os.path.isdir(folder):
        return

    # 1. Delete current outputs for requested types
    prefix_patterns = []
    if generation_mode.get("persona", False):
        prefix_patterns.append(f"{patient_id}-")
    if generation_mode.get("reports", False):
        prefix_patterns.append(f"DOC-{patient_id}-")
    if generation_mode.get("summary", False):
        prefix_patterns.append(f"Clinical_Summary_Patient_{patient_id}")

    for fname in os.listdir(folder):
        if fname == "archive" or not fname.endswith(".pdf"):
            continue
        if any(fname.startswith(p) for p in prefix_patterns):
            try:
                os.remove(os.path.join(folder, fname))
            except Exception:
                pass

    # 2. Move archived files back
    archive_dir = get_patient_archive_folder(patient_id)
    token_prefix = f"{archive_token}__"
    if os.path.isdir(archive_dir):
        for fname in os.listdir(archive_dir):
            if not fname.endswith(".pdf") or not fname.startswith(token_prefix):
                continue
            orig = fname[len(token_prefix):]
            try:
                shutil.move(os.path.join(archive_dir, fname), os.path.join(folder, orig))
            except Exception:
                pass

def sanitize_filename_component(name: str) -> str:
    """Make a safe filename segment across OSes."""
    if not name:
        return "document"
    name = name.replace(os.sep, "-").replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]+', "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name
