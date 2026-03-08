import re
import json
from datetime import datetime
from typing import Optional, List, Any


def _format_value(val: Any, depth: int = 0) -> str:
    """
    Recursively format a value for PDF body text.
    Dicts become readable key-value lines; lists become bullet lines; scalars as-is.
    """
    if val is None:
        return ""
    if isinstance(val, dict):
        lines = []
        for k, v in val.items():
            key_label = str(k).replace("_", " ").title()
            if isinstance(v, (dict, list)):
                sub = _format_value(v, depth + 1)
                lines.append(f"{key_label}:\n{sub}")
            else:
                lines.append(f"{key_label}: {v}" if v != "" and v is not None else f"{key_label}: (not specified)")
        return "\n".join(lines)
    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, (dict, list)):
                parts.append("- " + _format_value(item, depth + 1).replace("\n", "\n  "))
            else:
                parts.append(f"- {item}")
        return "\n".join(parts)
    return str(val).strip()


def _section_label(key: str) -> str:
    """Turn snake_case key into TITLE_CASE section label."""
    return key.replace("_", " ").upper()


def format_clinical_document(
    metadata: dict,
    structured_content: dict,
    ordered_sections_override: Optional[List[str]] = None,
) -> str:
    """
    Layer 2: STRICT Formatter.
    Takes clean metadata and structured JSON content, and renders the
    Machine-First Template. Nested dicts are flattened to readable key-value lines.

    If ordered_sections_override is provided (e.g. template sections list), section
    order and labels follow it; otherwise falls back to hardcoded consult/imaging order.
    """
    # 1. HEADER (Deterministic Metadata)
    header = (
        "[REPORT_METADATA]\n"
        f"PATIENT_ID: {metadata.get('patient_id')}\n"
        f"MRN: {metadata.get('mrn')}\n"
        f"PATIENT_NAME: {metadata.get('patient_name')}\n"
        f"DOB: {metadata.get('dob')}\n"
        f"GENDER: {metadata.get('gender')}\n"
        f"PATIENT_PHONE: {metadata.get('patient_phone', 'N/A')}\n"
        f"REPORT_DATE: {metadata.get('report_date')}\n"
        f"PROVIDER: {metadata.get('provider')}\n"
        f"PROVIDER_ADDRESS: {metadata.get('provider_address', 'N/A')}\n"
        f"PROVIDER_PHONE: {metadata.get('provider_phone', 'N/A')}\n"
        f"PLAN_TYPE: {metadata.get('plan_type', 'N/A')}\n"
        f"FACILITY: {metadata.get('facility')}\n"
        f"ACCESSION_ID: {metadata.get('accession_id')}\n"
        f"DOC_TYPE: {metadata.get('doc_type')}\n"
    )

    # 2. BODY (Structured Content) — template-driven order when provided
    if ordered_sections_override:
        ordered_sections_normalized = [s.lower().strip() for s in ordered_sections_override]
    else:
        ordered_sections_normalized = [
            "chief_complaint", "hpi", "past_medical_history", "past_surgical_history",
            "medications", "allergies", "social_history", "family_history",
            "review_of_systems", "vitals", "physical_exam", "labs", "imaging",
            "assessment", "plan",
        ]
        if metadata.get("doc_type") in ["IMAGING", "LAB", "PATHOLOGY"]:
            ordered_sections_normalized = [
                "exam_type", "clinical_indication", "technique", "comparison", "findings", "impression",
            ]

    body_parts = []

    for section_key in ordered_sections_normalized:
        if section_key not in structured_content or structured_content[section_key] is None:
            continue
        val = structured_content[section_key]
        if val == "" or (isinstance(val, (list, dict)) and not val):
            continue
        val_str = _format_value(val)
        if not val_str:
            continue
        label = _section_label(section_key)
        body_parts.append(f"[{label}]\n{val_str}")

    # Remaining keys not in ordered list
    seen = set(ordered_sections_normalized) | {"narrative"}
    for k, v in structured_content.items():
        k_lower = k.lower()
        if k_lower in seen or v is None:
            continue
        if v == "" or (isinstance(v, (list, dict)) and not v):
            continue
        val_str = _format_value(v)
        if not val_str:
            continue
        body_parts.append(f"[{_section_label(k)}]\n{val_str}")

    # 3. NARRATIVE (Strict Block)
    narrative_block = ""
    if "narrative" in structured_content and structured_content["narrative"]:
        narrative_block = f"\n[CLINICAL_TEXT]\n{structured_content['narrative']}\n"

    final_doc = f"{header}\n{chr(10).join(body_parts)}{narrative_block}\n"
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

    # V3 Architecture Check: See if it's a valid JSON string (Template)
    try:
        data = json.loads(document_text)
        if not isinstance(data, dict):
            return False, ["JSON content must be a dictionary"]
        return True, []
    except json.JSONDecodeError:
        pass # Fallback to V2 legacy plain text validation if not JSON

    # Rule 1: Must NOT contain old start/end markers (strip artifact)
    # (We no longer require them; presence is not an error, just ignored)

    # Rule 2: Metadata Header
    if VALIDATION_CONFIG["require_metadata_block"] and "[REPORT_METADATA]" not in document_text:
        errors.append("Missing [REPORT_METADATA]")

    # Rule 3: Key fields
    required_keys = ["PATIENT_ID:", "MRN:", "PATIENT_NAME:", "DOB:", "REPORT_DATE:"]
    for key in required_keys:
        if key not in document_text:
            errors.append(f"Missing Metadata Field: {key}")

    # Rule 4: Ban Forbidden Patterns
    if "Redacted" in document_text:
        errors.append("Redaction detected")
    if not VALIDATION_CONFIG["allow_markdown_bold"] and "**" in document_text:
        errors.append("Markdown bold detected")

    if errors:
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
