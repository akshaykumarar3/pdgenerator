import os
import json
import uuid
import datetime
import random
from typing import Dict, Any

from . import patient_db

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(_BASE_DIR, "generated_output", "debug")

# Helper list of fictional insurance companies for random assignment if not provided
INSURANCE_PAYERS = [
    {"payer_id": "UHC-001", "name": "UnitedHealthcare", "plan_type": "PPO"},
    {"payer_id": "AET-002", "name": "Aetna", "plan_type": "HMO"},
    {"payer_id": "BCBS-003", "name": "Blue Cross Blue Shield", "plan_type": "EPO"},
    {"payer_id": "CIG-004", "name": "Cigna", "plan_type": "PPO"}
]

def ensure_debug_dir():
    os.makedirs(DEBUG_DIR, exist_ok=True)

def generate_new_identifiers(patient_id: str) -> Dict[str, str]:
    """Generates a fresh set of deterministic IDs."""
    curr_year = datetime.datetime.now().year
    return {
        "mrn": f"MRN-{patient_id}-{curr_year}",
        "insurance_member_id": f"MBR-{random.randint(100000, 999999)}",
        "policy_number": f"POL-{curr_year}-{random.randint(1000, 9999)}"
    }

def load_patient_state(patient_id: str) -> Dict[str, Any]:
    """Loads a previously saved patient state from the debug folder."""
    path = os.path.join(DEBUG_DIR, f"patient_state_{patient_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_patient_state(patient_id: str, state: Dict[str, Any]):
    """Saves the state to the debug folder."""
    ensure_debug_dir()
    path = os.path.join(DEBUG_DIR, f"patient_state_{patient_id}.json")
    with open(path, "w", encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def build_patient_state(patient_id: str, case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the canonical Patient State Layer.
    If the patient exists in patient_db, reuse their locked identities.
    Otherwise, initialize a template structure that the AI will fill,
    but lock in the core identifiers.
    """
    # 1. Load existing db record if present
    existing_record = patient_db.load_patient(patient_id)
    
    # 2. Setup Base State
    identifiers = {}
    demographics = {}
    
    if existing_record:
        # User already generated a persona for this ID; reuse data
        identifiers = existing_record.get("identifiers", {})
        if not identifiers:
             # Retrofit for legacy db entries that lacked the 'identifiers' block
             curr_year = datetime.datetime.now().year
             mrn = existing_record.get("mrn", f"MRN-{patient_id}-{curr_year}")
             payer_info = existing_record.get("payer", {})
             identifiers = {
                 "mrn": mrn,
                 "insurance_member_id": payer_info.get("member_id", f"MBR-{random.randint(100000, 999999)}"),
                 "policy_number": payer_info.get("policy_number", f"POL-{curr_year}-{random.randint(1000, 9999)}")
             }

        demographics = {
            "name": f"{existing_record.get('first_name', '')} {existing_record.get('last_name', '')}".strip(),
            "dob": existing_record.get("dob", "1970-01-01"),
            "gender": existing_record.get("gender", "Unknown"),
            "race": existing_record.get("race", "Unknown"),
            "height": existing_record.get("height", "Unknown"),
            "weight": existing_record.get("weight", "Unknown"),
            "address": existing_record.get("address", ""),
            "phone": existing_record.get("telecom", "")
        }
    else:
        # Generate entirely new core identifiers. 
        # The AI will fill in demographics (Name, DOB, Race) and we will save it back later.
        identifiers = generate_new_identifiers(patient_id)
        # Demographics remain empty for AI to populate in the 'persona' generation phase.
        demographics = {
            "name": "",
            "dob": "",
            "gender": "",
            "race": "",
            "height": "",
            "weight": "",
            "address": "",
            "phone": ""
        }

    # 3. Assemble Full State Object 
    # (Leaving medical details empty or minimally seeded by case_data for AI to expand)
    
    # We create a structured JSON payload conforming to the V3 Architectures Patient State Layer
    
    # Extract diagnoses from case_data details if possible, otherwise will be generated
    diagnoses = []
    
    procedure_name = case_data.get("procedure", "Unknown Procedure")
    # CPT code from case_data or procedure text
    cpt_code = str(case_data.get("cpt_code", "") or "").strip()
    if not cpt_code and procedure_name:
        import re
        m = re.search(r"(\\d{5})", str(procedure_name))
        if m:
            cpt_code = m.group(1)
    
    # Pick random insurance for new patients
    selected_payer = random.choice(INSURANCE_PAYERS)
    
    patient_state = {
        "patient_id": str(patient_id),
        "identifiers": identifiers,
        "demographics": demographics,
        "providers": [], # To be filled by AI
        "diagnoses": diagnoses,
        "medications": [],
        "allergies": [],
        "timeline": {}, # Will be filled by AI / Generator temporal helpers
        "requested_procedure": {
             "procedure_name": procedure_name,
             "cpt_code": cpt_code,
             "expected_date": "" # Handled by generate temporal logic later
        },
        "insurance": {
             "payer_id": selected_payer["payer_id"],
             "payer_name": selected_payer["name"],
             "plan_type": selected_payer["plan_type"],
             "member_id": identifiers["insurance_member_id"],
             "policy_number": identifiers["policy_number"]
        }
    }
    
    # Save debug
    save_patient_state(patient_id, patient_state)
    
    return patient_state
