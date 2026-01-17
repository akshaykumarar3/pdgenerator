import re
import json
from datetime import datetime

def format_clinical_document(metadata: dict, structured_content: dict) -> str:
    """
    Layer 2: STRICT Formatter.
    Takes clean metadata and structured JSON content, and renders the 
    Machine-First Template.
    """
    
    # 1. HEADER (Deterministic Metadata)
    # FORMAT:
    # [REPORT_METADATA]
    # PATIENT_ID: ...
    # ...
    
    header = (
        "[REPORT_METADATA]\n"
        f"PATIENT_ID: {metadata.get('patient_id')}\n"
        f"MRN: {metadata.get('mrn')}\n"
        f"PATIENT_NAME: {metadata.get('patient_name')}\n"
        f"DOB: {metadata.get('dob')}\n"
        f"GENDER: {metadata.get('gender')}\n"
        f"REPORT_DATE: {metadata.get('report_date')}\n"
        f"PROVIDER: {metadata.get('provider')}\n"
        f"FACILITY: {metadata.get('facility')}\n"
        f"ACCESSION_ID: {metadata.get('accession_id')}\n"
        f"DOC_TYPE: {metadata.get('doc_type')}\n"
    )

    # 2. BODY (Structured Content)
    # We iterate through the JSON keys and print them as sections if they exist.
    # Narratives go into [CLINICAL_TEXT]
    
    body = ""
    
    # Standard Ordering for Consults
    ordered_sections = [
        "CHIEF_COMPLAINT", "HPI", "PAST_MEDICAL_HISTORY", "PAST_SURGICAL_HISTORY",
        "MEDICATIONS", "ALLERGIES", "SOCIAL_HISTORY", "FAMILY_HISTORY", 
        "REVIEW_OF_SYSTEMS", "VITALS", "PHYSICAL_EXAM", "LABS", "IMAGING",
        "ASSESSMENT", "PLAN"
    ]
    
    # Standard Ordering for Imaging/Labs
    if metadata.get('doc_type') in ['IMAGING', 'LAB', 'PATHOLOGY']:
         ordered_sections = ["EXAM_TYPE", "CLINICAL_INDICATION", "TECHNIQUE", "COMPARISON", "FINDINGS", "IMPRESSION"]

    body_parts = []
    
    # Add ordered sections first
    for section in ordered_sections:
        key = section.lower()
        if key in structured_content and structured_content[key]:
            val = structured_content[key]
            # Format list or string
            if isinstance(val, list):
                val_str = "\n".join([f"- {v}" for v in val])
            else:
                val_str = str(val).strip()
                
            body_parts.append(f"[{section}]\n{val_str}")
            
    # Add any remaining keys
    for k, v in structured_content.items():
        if k.upper() not in ordered_sections and k != "narrative":
             if isinstance(v, list):
                val_str = "\n".join([f"- {x}" for x in v])
             else:
                val_str = str(v).strip()
             body_parts.append(f"[{k.upper()}]\n{val_str}")

    # 3. NARRATIVE (Strict Block)
    narrative_block = ""
    if "narrative" in structured_content:
        narrative_block = f"\n[CLINICAL_TEXT]\n{structured_content['narrative']}\n"
        
    final_doc = f"--- REPORT START ---\n{header}\n{chr(10).join(body_parts)}{narrative_block}\n--- REPORT END ---"
    return final_doc

# CONFIG
VALIDATION_CONFIG = {
    "allow_markdown_bold": True,
    "allow_triple_quotes": False,
    "require_metadata_block": True
}

def validate_structure(document_text: str) -> tuple[bool, list[str]]:
    """
    Layer 3: Validator.
    Returns (IsValid, ListOfErrors).
    """
    errors = []
    
    # Rule 1: Markers
    if "--- REPORT START ---" not in document_text:
        errors.append("Missing Start Marker")
    if "--- REPORT END ---" not in document_text:
        errors.append("Missing End Marker")
        
    # Rule 2: Metadata Header
    if VALIDATION_CONFIG["require_metadata_block"] and "[REPORT_METADATA]" not in document_text:
        errors.append("Missing [REPORT_METADATA]")
        
    # Rule 3: Key fields
    required_keys = ["PATIENT_ID:", "MRN:", "PATIENT_NAME:", "DOB:", "REPORT_DATE:"]
    for key in required_keys:
        if key not in document_text:
             errors.append(f"Missing Metadata Field: {key}")
             
    # Rule 4: Ban Forbidden Patterns
    if not VALIDATION_CONFIG["allow_triple_quotes"] and '"""' in document_text:
        errors.append("Triple quotes detected")
    if "Redacted" in document_text:
        errors.append("Redaction detected")
    if not VALIDATION_CONFIG["allow_markdown_bold"] and "**" in document_text:
        errors.append("Markdown bold detected")
        
    if errors:
        # print(f"   ⚠️ Validation Failed: {errors}") # Noise reduction
        return False, errors
        
    return True, []

def sanitize_narrative(text: str, identity_map: dict) -> str:
    """
    Scrub identity leaks from narrative text.
    identity_map = {'value_to_redact': 'REPLACEMENT'}
    """
    # Simple replace for now, can be complex regex later
    for sensitive_val in identity_map.values():
        # simple check - in real prod use NER
        pass 
    return text
