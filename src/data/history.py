import os
from datetime import datetime

from ..core.config import get_patient_logs_folder

def get_history(patient_id: str) -> str:
    """
    Reads the history log for a patient.
    Returns the content string or empty string if no log exists.
    """
    log_dir = get_patient_logs_folder(patient_id)
    log_path = os.path.join(log_dir, f"{patient_id}.txt")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            return f.read()

    return ""

def append_history(patient_id: str, feedback: str, changes_summary: str):
    """
    Appends a new entry to the patient's history log.
    FORMAT: [YYYY-MM-DD HH:MM] Feedback: <text> | Changes: <text>
    """
    log_dir = get_patient_logs_folder(patient_id)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_path = os.path.join(log_dir, f"{patient_id}.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"\n--------------------------------------------------\n"
    entry += f"RUN TIMESTAMP: {timestamp}\n"
    entry += f"USER FEEDBACK: {feedback if feedback else 'None'}\n"
    entry += f"AI CHANGES: {changes_summary}\n"
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
