import os
import re
from dotenv import load_dotenv

# Load environment variables from cred/.env relative to project root
# __file__ is src/core/config.py → project root is three levels up.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_project_root, "cred", ".env")
load_dotenv(_env_path)

OUTPUT_DIR = os.getenv("OUTPUT_DIR") or os.path.join(_project_root, "generated_output")
PATIENT_DATA_DIR = os.path.join(OUTPUT_DIR, "patient-data")
DEBUG_DIR = os.path.join(OUTPUT_DIR, "debug")


def ensure_output_dirs():
    """Create all required output directories if they do not exist."""
    for d in [OUTPUT_DIR, PATIENT_DATA_DIR, DEBUG_DIR]:
        os.makedirs(d, exist_ok=True)

def _safe_folder_component(name: str) -> str:
    if not name:
        return "Unknown"
    name = name.replace(os.sep, "-").replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]+', "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Unknown"

def _resolve_patient_name(patient_id: str, patient_name: str | None = None) -> str:
    if patient_name:
        return patient_name
    try:
        from . import patient_db
        p = patient_db.load_patient(patient_id)
        if p:
            full = " ".join([p.get("first_name", ""), p.get("last_name", "")]).strip()
            if full:
                return full
    except Exception:
        pass
    return "Unknown"

def find_patient_folder(patient_id: str) -> str | None:
    if not os.path.isdir(PATIENT_DATA_DIR):
        return None
    prefix = f"{patient_id} -"
    for entry in os.listdir(PATIENT_DATA_DIR):
        if entry.startswith(prefix):
            return os.path.join(PATIENT_DATA_DIR, entry)
    return None

def get_patient_root(patient_id: str, patient_name: str | None = None, prefer_name: bool = False) -> str:
    """Root output folder for a patient (patient_id - name - cpt - outcome)."""
    if not prefer_name:
        existing = find_patient_folder(patient_id)
        if existing:
            return existing
    resolved_name = _resolve_patient_name(patient_id, patient_name)
    safe_name = _safe_folder_component(resolved_name)
    
    # Extract CPT Code and Outcome
    try:
        from ..data import loader as data_loader
        case_data = data_loader.get_case_details(patient_id) or {}
        cpt_code = str(case_data.get("cpt_code", "Unknown")).strip() or "Unknown"
        outcome = str(case_data.get("outcome", "Unknown")).strip() or "Unknown"
    except Exception:
        cpt_code = "Unknown"
        outcome = "Unknown"
        
    safe_cpt = _safe_folder_component(cpt_code)
    safe_outcome = _safe_folder_component(outcome)

    folder_name = f"{patient_id} - {safe_name} - {safe_cpt} - {safe_outcome}"
    return os.path.join(PATIENT_DATA_DIR, folder_name)

def get_patient_persona_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Persona PDFs folder for a patient (root)."""
    return get_patient_root(patient_id, patient_name)

def get_patient_report_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Report PDFs folder for a patient (root)."""
    return get_patient_root(patient_id, patient_name)

def get_patient_summary_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Summary PDFs folder for a patient (root)."""
    return get_patient_root(patient_id, patient_name)

def get_patient_archive_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Archive folder for a patient."""
    p_root = get_patient_root(patient_id, patient_name)
    folder_name = os.path.basename(p_root)
    return os.path.join(OUTPUT_DIR, "archive", folder_name)

def get_patient_logs_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Logs folder for a patient."""
    p_root = get_patient_root(patient_id, patient_name)
    folder_name = os.path.basename(p_root)
    return os.path.join(OUTPUT_DIR, "logs", folder_name)

def get_patient_records_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Text record folder containing metadata."""
    p_root = get_patient_root(patient_id, patient_name)
    folder_name = os.path.basename(p_root)
    return os.path.join(OUTPUT_DIR, "metadata", folder_name)

def get_patient_debug_folder(patient_id: str, patient_name: str | None = None) -> str:
    """Debug state folder for a patient."""
    p_root = get_patient_root(patient_id, patient_name)
    folder_name = os.path.basename(p_root)
    return os.path.join(DEBUG_DIR, folder_name)


__all__ = [
    "OUTPUT_DIR",
    "PATIENT_DATA_DIR",
    "ensure_output_dirs",
    "find_patient_folder",
    "get_patient_root",
    "get_patient_persona_folder",
    "get_patient_report_folder",
    "get_patient_summary_folder",
    "get_patient_archive_folder",
    "get_patient_logs_folder",
    "get_patient_records_folder",
    "DEBUG_DIR",
    "get_patient_debug_folder",
]
