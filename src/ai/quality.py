import json
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

# Assuming models are in a sibling file
from . import models
from . import prompts

# Vertex AI REST context window: gemini-1.5-pro supports up to ~1M tokens input,
# but keeping the prompt under ~80K characters (≈20K tokens) ensures the model
# has enough budget to emit a full clinical payload without truncation.
_PROMPT_CHAR_BUDGET = 80_000


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    val = str(val).strip()
    return val if val else default


def _calc_age(dob_str: str) -> Optional[int]:
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str, "%m-%d-%Y").date()
        today = datetime.now().date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def _dedupe_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _extract_supporting_diagnoses(persona) -> List[str]:
    dx = []
    if persona and getattr(persona, "pa_request", None):
        dx.extend(getattr(persona.pa_request, "supporting_diagnoses", []) or [])
    if persona and getattr(persona, "encounters", None):
        for enc in persona.encounters or []:
            dx.extend(getattr(enc, "diagnoses", []) or [])
    return _dedupe_preserve(dx)


def _extract_medications(persona, max_items: int = 4) -> List[str]:
    meds = []
    for m in (getattr(persona, "medications", None) or [])[:max_items]:
        brand = _safe_str(getattr(m, "brand", ""))
        generic = _safe_str(getattr(m, "generic_name", ""))
        dosage = _safe_str(getattr(m, "dosage", ""))
        name = brand or generic
        if name and generic and brand and brand != generic:
            name = f"{brand} ({generic})"
        if dosage:
            name = f"{name} {dosage}".strip()
        if name:
            meds.append(name)
    return meds


def _extract_procedures(persona, max_items: int = 3) -> List[str]:
    procs = []
    for p in (getattr(persona, "procedures", None) or [])[:max_items]:
        name = _safe_str(getattr(p, "name", ""))
        date = _safe_str(getattr(p, "date", ""))
        reason = _safe_str(getattr(p, "reason", ""))
        if name:
            detail = f"{name} ({date})" if date else name
            if reason:
                detail = f"{detail} for {reason}"
            procs.append(detail)
    return procs


def _extract_therapies(persona, max_items: int = 3) -> List[str]:
    therapies = []
    for t in (getattr(persona, "therapies", None) or [])[:max_items]:
        t_type = _safe_str(getattr(t, "therapy_type", ""))
        reason = _safe_str(getattr(t, "reason", ""))
        if t_type:
            therapies.append(f"{t_type} for {reason}".strip() if reason else t_type)
    return therapies


def _summarize_encounters(persona, max_items: int = 2) -> List[str]:
    summaries = []
    encounters = getattr(persona, "encounters", None) or []
    for enc in encounters[:max_items]:
        date = _safe_str(getattr(enc, "encounter_date", ""))
        enc_type = _safe_str(getattr(enc, "encounter_type", ""))
        complaint = _safe_str(getattr(enc, "chief_complaint", ""))
        purpose = _safe_str(getattr(enc, "purpose_of_visit", ""))
        if date or enc_type or complaint:
            parts = []
            if date:
                parts.append(f"On {date}")
            if enc_type:
                parts.append(f"{enc_type.lower()} visit")
            if complaint:
                parts.append(f"for {complaint}")
            elif purpose:
                parts.append(f"for {purpose}")
            summaries.append(" ".join(parts).strip() + ".")
    return summaries


def _build_bio_narrative(persona, case_details: dict, patient_state: dict) -> str:
    name = _safe_str(f"{getattr(persona, 'first_name', '')} {getattr(persona, 'last_name', '')}".strip(), "The patient")
    gender = _safe_str(getattr(persona, "gender", ""))
    dob = _safe_str(getattr(persona, "dob", ""))
    age = _calc_age(dob)
    age_str = f"{age}-year-old" if age is not None else "adult"
    address = _safe_str(getattr(persona, "address", ""), "Texas")
    procedure = _safe_str(getattr(persona, "procedure_requested", ""), _safe_str(case_details.get("procedure", "")))
    expected_date = _safe_str(getattr(persona, "expected_procedure_date", ""), _safe_str(patient_state.get("requested_procedure", {}).get("expected_date", "")))
    cpt_code = _safe_str(patient_state.get("requested_procedure", {}).get("cpt_code", ""))
    if not cpt_code and procedure:
        match = re.search(r"(\\d{5})", procedure)
        if match:
            cpt_code = match.group(1)
    cpt_text = f"CPT {cpt_code}" if cpt_code else "the requested CPT"

    dx_list = _extract_supporting_diagnoses(persona)
    dx_text = ", ".join(dx_list[:4]) if dx_list else "clinically documented conditions"
    meds = _extract_medications(persona)
    meds_text = ", ".join(meds) if meds else "medications appropriate for the above conditions"
    procs = _extract_procedures(persona)
    procs_text = "; ".join(procs) if procs else "no prior operative history of note"
    therapies = _extract_therapies(persona)
    therapies_text = ", ".join(therapies) if therapies else "supportive therapy as clinically indicated"

    social = getattr(persona, "social_history", None)
    tobacco = _safe_str(getattr(social, "tobacco_use", ""), "denies tobacco use") if social else "denies tobacco use"
    alcohol = _safe_str(getattr(social, "alcohol_use", ""), "reports minimal alcohol use") if social else "reports minimal alcohol use"
    family_history = _safe_str(getattr(social, "family_history_relevant", ""), "family history reviewed with no major hereditary risk noted") if social else "family history reviewed with no major hereditary risk noted"

    enc_summaries = _summarize_encounters(persona)
    enc_text = " ".join(enc_summaries) if enc_summaries else "Recent clinical encounters document persistent symptoms and functional impact."

    case_details_text = _safe_str(case_details.get("details", ""))
    if case_details_text:
        case_details_text = _sanitize_judgment_text(case_details_text)
    expected_outcome = _safe_str(case_details.get("outcome", ""))

    para1 = (
        f"{name} is a {age_str} {gender} from {address} presenting for evaluation related to {procedure or 'the requested procedure'}. "
        f"The referral is tied to {cpt_text} with an anticipated procedure date of {expected_date or 'the upcoming weeks'}. "
        f"Key diagnoses include {dx_text}."
    )
    para2 = (
        f"{enc_text} "
        f"Symptoms have progressed over months with measurable impact on daily function and work capacity. "
        f"{case_details_text}" if case_details_text else
        f"{enc_text} Symptoms have progressed over months with measurable impact on daily function and work capacity."
    )
    para3 = (
        f"Past medical history is notable for {dx_text}. "
        f"Prior procedures and interventions include {procs_text}. "
        f"Current and recent medications include {meds_text}. "
        f"Therapy history includes {therapies_text}."
    )
    para4 = (
        f"Social history: {tobacco}; {alcohol}. "
        f"Family history: {family_history}. "
        f"The record documents persistent symptoms despite conservative management and objective findings aligned with the above diagnoses. "
        f"The requested procedure has been planned accordingly."
    )

    paragraphs = [para1, para2, para3, para4]
    narrative = "\n\n".join([p.strip() for p in paragraphs if p and p.strip()])

    # Ensure narrative length target
    if _word_count(narrative) < 300:
        extra = (
            "Additional documentation across encounters includes objective findings and response patterns to prior conservative management. "
            "Imaging and lab results in the chart align with the above diagnoses."
        )
        narrative = narrative + "\n\n" + extra

    if _word_count(narrative) < 300:
        narrative = narrative + "\n\n" + (
            "The longitudinal record shows adherence to follow-up plans and evolving symptom burden despite treatment."
        )

    return narrative.strip()


def _load_sanitization_patterns() -> List[str]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "sanitization_patterns.json")
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            return data.get("patterns", [])
    except (IOError, json.JSONDecodeError):
        return []

_DISALLOWED_JUDGMENT_PATTERNS = _load_sanitization_patterns()

def _sanitize_judgment_text(text: str) -> str:
    if not text:
        return text
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    kept = []
    for part in parts:
        if not part:
            continue
        lowered = part.lower()
        if any(re.search(pat, lowered, re.IGNORECASE) for pat in _DISALLOWED_JUDGMENT_PATTERNS):
            continue
        kept.append(part.strip())
    cleaned = " ".join(kept).strip()
    if not cleaned:
        cleaned = "Relevant clinical findings are documented in this note."
    return cleaned


def _sanitize_document_content(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text and text[0] in "{[":
            try:
                parsed = json.loads(text)
                return _sanitize_document_content(parsed)
            except Exception:
                pass
        return _sanitize_judgment_text(value)
    if isinstance(value, list):
        return [_sanitize_document_content(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_document_content(v) for k, v in value.items()}
    return value


def ensure_persona_quality(payload: "models.ClinicalDataPayload", case_details: dict, patient_state: dict) -> "models.ClinicalDataPayload":
    if not payload or not getattr(payload, "patient_persona", None):
        return payload
    persona = payload.patient_persona
    def _pad_bio(text: str) -> str:
        if _word_count(text) >= 300:
            return text
        fillers = [
            "The chart reflects ongoing symptom tracking, routine follow-up, and consistent documentation of clinical findings.",
            "Prior conservative measures, medication adjustments, and lifestyle modifications are recorded with response trends.",
            "Relevant findings are summarized alongside encounter dates to maintain a clear longitudinal timeline.",
        ]
        out = text
        for f in fillers:
            if _word_count(out) >= 300:
                break
            out = out + "\n\n" + f
        return out

    bio = _safe_str(getattr(persona, "bio_narrative", ""))
    if _word_count(bio) < 300:
        bio = _build_bio_narrative(persona, case_details, patient_state)
    bio_clean = _sanitize_judgment_text(bio)
    if _word_count(bio_clean) < 300:
        bio_clean = _build_bio_narrative(persona, case_details, patient_state)
        bio_clean = _sanitize_judgment_text(bio_clean)
    persona.bio_narrative = _pad_bio(bio_clean)
    # Sanitize PA clinical justification to avoid judgment language
    pa_request = getattr(persona, "pa_request", None)
    if pa_request and hasattr(pa_request, "clinical_justification"):
        pa_request.clinical_justification = _sanitize_judgment_text(
            _safe_str(getattr(pa_request, "clinical_justification", ""))
        )
    payload.patient_persona = persona

    # Backfill report medical history sections when missing
    if getattr(payload, "documents", None):
        for doc in payload.documents:
            content = getattr(doc, "content", None)
            structured = None
            if isinstance(content, dict):
                structured = content
            elif isinstance(content, str):
                try:
                    structured = json.loads(content)
                except Exception:
                    structured = None
            if not isinstance(structured, dict):
                continue
            key = "past_medical_history"
            if key in structured:
                val = structured.get(key)
                is_blank = val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and len(val) == 0)
                if is_blank:
                    history_items = _extract_supporting_diagnoses(persona)
                    if not history_items:
                        detail = _safe_str(case_details.get("details", ""))
                        history_items = [detail] if detail else ["History notable for symptoms prompting the requested procedure."]
                    structured[key] = history_items
                    doc.content = structured
            # Sanitize judgment language in document body text
            doc.content = _sanitize_document_content(doc.content)
    return payload


def quantize_prompt(
    prompt: str,
    case_details: dict,
    patient_state: dict,
    document_plan: dict,
    user_feedback: str,
    history_context: str,
    existing_persona,
) -> str:
    """
    If the assembled prompt exceeds _PROMPT_CHAR_BUDGET characters, progressively
    deflate the least-critical sections to bring it within budget:

    Pass 1 — Trim history_context to its first 2000 characters.
    Pass 2 — Drop individual template bodies from document_plan (keep keys only).
    Pass 3 — Trim the assembled prompt hard at budget boundary with a warning appended.
    """
    if len(prompt) <= _PROMPT_CHAR_BUDGET:
        return prompt

    print(f"   ⚠️  Prompt too large ({len(prompt):,} chars > {_PROMPT_CHAR_BUDGET:,}). Quantizing…")

    # Pass 1: trim history_context
    if history_context and len(history_context) > 2000:
        history_context = history_context[:2000] + "\n[...history truncated for context budget...]"
        prompt = prompts.get_clinical_data_prompt(
            case_details=case_details,
            patient_state=patient_state,
            document_plan=document_plan,
            user_feedback=user_feedback,
            history_context=history_context,
            existing_persona=existing_persona,
        )
        print(f"   ⚠️  Pass 1 — history trimmed → {len(prompt):,} chars")

    if len(prompt) <= _PROMPT_CHAR_BUDGET:
        return prompt

    # Pass 2: strip template bodies, keep only template filenames
    slim_plan = dict(document_plan)
    if isinstance(slim_plan.get("document_templates"), dict):
        slim_plan["document_templates"] = {
            k: {"_note": "template body omitted to reduce context"}
            for k in slim_plan["document_templates"]
        }
        prompt = prompts.get_clinical_data_prompt(
            case_details=case_details,
            patient_state=patient_state,
            document_plan=slim_plan,
            user_feedback=user_feedback,
            history_context=history_context,
            existing_persona=existing_persona,
        )
        print(f"   ⚠️  Pass 2 — templates slimmed → {len(prompt):,} chars")

    if len(prompt) <= _PROMPT_CHAR_BUDGET:
        return prompt

    # Pass 3: hard truncation at budget
    print(f"   ⚠️  Pass 3 — hard truncation applied")
    return prompt[:_PROMPT_CHAR_BUDGET] + "\n\n[CONTEXT TRUNCATED — generate best clinical output from available data]"
