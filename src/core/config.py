import os
from dotenv import load_dotenv

# Load environment variables from cred/.env relative to project root
# __file__ is src/core/config.py → project root is three levels up.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_project_root, "cred", ".env")
load_dotenv(_env_path)

OUTPUT_DIR = os.getenv("OUTPUT_DIR") or os.path.join(_project_root, "generated_output")

PERSONA_DIR = os.path.join(OUTPUT_DIR, "persona")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "patient-reports")
SUMMARY_DIR = os.path.join(OUTPUT_DIR, "summary")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
RECORDS_DIR = os.path.join(OUTPUT_DIR, "records")


def ensure_output_dirs():
    """Create all required output directories if they do not exist."""
    for d in [OUTPUT_DIR, PERSONA_DIR, REPORTS_DIR, SUMMARY_DIR, LOGS_DIR, RECORDS_DIR]:
        os.makedirs(d, exist_ok=True)


def get_patient_report_folder(patient_id: str) -> str:
    """Helper to get the specific report output folder for a patient."""
    return os.path.join(REPORTS_DIR, str(patient_id))
