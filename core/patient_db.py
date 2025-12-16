import json
import os
from typing import Optional, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "patients_db.json")

def _init_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, 'w') as f:
            json.dump({}, f)

def load_patient(patient_id: str) -> Optional[Dict]:
    """
    Loads patient data (name, db, gender, persona) from the central JSON DB.
    Returns None if not found.
    """
    _init_db()
    with open(DB_PATH, 'r') as f:
        data = json.load(f)
    
    # Handle both string/int keys
    key = str(patient_id)
    return data.get(key)

def save_patient(patient_id: str, patient_data: Dict):
    """
    Saves or updates patient data in the central JSON DB.
    patient_data should include: name, dob, gender, persona_content, etc.
    """
    _init_db()
    
    # Read strict
    with open(DB_PATH, 'r') as f:
        current_db = json.load(f)
    
    # Update
    key = str(patient_id)
    if key not in current_db:
        current_db[key] = {}
    
    current_db[key].update(patient_data)
    
    # Write back
    with open(DB_PATH, 'w') as f:
        json.dump(current_db, f, indent=2)
    
    print(f"      💾 Patient {patient_id} ({patient_data.get('name', 'Unknown')}) saved to Core DB.")

def get_all_patient_names() -> list[str]:
    """
    Returns a list of all 'First Last' names currently in the DB.
    Used to prevent duplicate personas.
    """
    _init_db()
    try:
        with open(DB_PATH, 'r') as f:
            data = json.load(f)
        
        names = []
        for pid, p_data in data.items():
            fname = p_data.get('first_name', '')
            lname = p_data.get('last_name', '')
            if fname and lname:
                names.append(f"{fname} {lname}")
        return names
    except Exception:
        return []
