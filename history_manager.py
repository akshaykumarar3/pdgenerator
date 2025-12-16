import os
from datetime import datetime

LOG_FOLDER = "logs"

def get_history(patient_id: str) -> str:
    """
    Reads the history log for a patient.
    Returns the content string or empty string if no log exists.
    """
    if not os.path.exists(LOG_FOLDER):
        return ""
        
    log_path = os.path.join(LOG_FOLDER, f"{patient_id}.txt")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            return f.read()
    return ""

def append_history(patient_id: str, feedback: str, changes_summary: str):
    """
    Appends a new entry to the patient's history log.
    FORMAT: [YYYY-MM-DD HH:MM] Feedback: <text> | Changes: <text>
    """
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)
        
    log_path = os.path.join(LOG_FOLDER, f"{patient_id}.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"\n--------------------------------------------------\n"
    entry += f"RUN TIMESTAMP: {timestamp}\n"
    entry += f"USER FEEDBACK: {feedback if feedback else 'None'}\n"
    entry += f"AI CHANGES: {changes_summary}\n"
    
    with open(log_path, 'a') as f:
        f.write(entry)
