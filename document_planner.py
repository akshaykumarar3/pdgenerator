import os
import json
import re
from typing import List, Dict

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(_BASE_DIR, "generated_output", "debug")
RULES_PATH = os.path.join(_BASE_DIR, "templates", "document_plan_rules.json")

def ensure_debug_dir():
    try:
        if not os.path.exists(DEBUG_DIR):
            try:
                os.makedirs(DEBUG_DIR, exist_ok=True)
            except Exception as e:
                # Ignore errors here to prevent blocking main flow
                pass
        elif not os.path.isdir(DEBUG_DIR):
            print(f"⚠️ Warning: {DEBUG_DIR} is not a directory.")
    except Exception as e:
        print(f"⚠️ Could not ensure debug dir: {e}")

def load_rules() -> Dict:
    """Loads document plan rules from the templates directory."""
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {RULES_PATH}: {e}")
    return {}

def detect_case_type(procedure_string: str) -> str:
    """
    Detects the case type string based on the provided CPT code or procedure string.
    Rules:
    70000–79999 → 'imaging'
    10000–69999 → 'surgery'
    97000–97999 → 'therapy'
    medication keywords -> 'medication'
    default → 'diagnostic'
    """
    if not procedure_string:
        return "diagnostic"
        
    rules = load_rules()
    
    # Extract CPT from procedure string if supplied (often structured like 'CPT: 75574' or just '75574')
    cpt_match = re.search(r"(\d{5})", str(procedure_string))
    cpt_code = None
    if cpt_match:
        cpt_code = cpt_match.group(1)
        # Attempt integer parsing for ranges
        try:
            cpt_int = int(cpt_code)
            if 10000 <= cpt_int <= 69999:
                return "surgery"
            elif 70000 <= cpt_int <= 79999:
                return "imaging"
            elif 97000 <= cpt_int <= 97999:
                return "therapy"
        except Exception:
            pass
            
    # Fallback to keyword matching for medications
    proc_lower = str(procedure_string).lower()
    med_keywords = rules.get("medication", {}).get("keywords", ["infusion", "injection", "prescription", "medication", "drug"])
    for kw in med_keywords:
        if kw in proc_lower:
            return "medication"
            
    # Default
    return "diagnostic"

def select_document_plan(case_type: str) -> List[str]:
    """
    Loads templates/document_plan_rules.json and returns a list of template filenames
    for the specified case_type.
    """
    rules = load_rules()
    if case_type in rules:
        return rules[case_type].get("templates", [])
    
    # Fallback default plan
    return ["prior_auth_request_template.json", "summary_template.json"]

def create_and_save_document_plan(patient_id: str, case_data: Dict) -> Dict:
    """
    Orchestration wrapper that detects case type, loads the plan templates,
    and writes out the debug plan representation.
    """
    procedure = case_data.get("procedure", "")
    case_type = detect_case_type(procedure)
    templates = select_document_plan(case_type)
    
    plan = {
        "case_type": case_type,
        "procedure": procedure,
        "document_templates": templates
    }
    
    ensure_debug_dir()
    path = os.path.join(DEBUG_DIR, "document_plan.json")
    with open(path, "w", encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
        
    return plan
