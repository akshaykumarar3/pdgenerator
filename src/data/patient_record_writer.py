"""
patient_record_writer.py
========================
Writes/updates a human-readable patient text record after each generation.
Location: records/{patient_id}-record.txt

Sections:
  - Patient Identity
  - Insurance
  - Provider
  - Current Vitals
  - Social History
  - Encounters (summary)
  - Medications
  - Allergies
  - Vaccinations
  - Therapies
  - Behavioral Notes
  - Gender-Specific History
  - PA Request
  - Document Index (versioned)
  - Feedback Log
"""

import os
from datetime import datetime

from ..core.config import get_patient_records_folder


def _hr(width: int = 70) -> str:
    return "=" * width + "\n"


def _section(title: str) -> str:
    return f"\n{'─' * 70}\n  {title.upper()}\n{'─' * 70}\n"


def _val(label: str, value, indent: int = 2) -> str:
    pad = " " * indent
    if value is None or value == "" or value == []:
        return f"{pad}{label}: (not recorded)\n"
    return f"{pad}{label}: {value}\n"


def write_patient_record(
    patient_id: str,
    persona,                  # PatientPersona (Pydantic) or dict
    version: int,
    docs_generated: list,     # list of filenames written this run
    feedback: str = "",
) -> str:
    """
    Write/overwrite records/{patient_id}-record.txt.
    Returns the path to the file.
    """
    records_dir = get_patient_records_folder(patient_id)
    os.makedirs(records_dir, exist_ok=True)
    out_path = os.path.join(records_dir, f"{patient_id}-record.txt")

    # Support both Pydantic and plain dict
    if hasattr(persona, "model_dump"):
        p = persona.model_dump()
    else:
        p = persona or {}

    now = datetime.now().strftime("%m-%d-%Y %H:%M:%S")

    # ── helpers ──────────────────────────────────────────────────────────────
    def g(key, default="(not recorded)"):
        v = p.get(key)
        return v if v not in (None, "", [], {}) else default

    def nested(key):
        return p.get(key) or {}

    lines = []

    # ── HEADER ────────────────────────────────────────────────────────────────
    lines.append(_hr())
    lines.append(f"  PATIENT RECORD\n")
    lines.append(f"  Patient ID : {patient_id}\n")
    lines.append(f"  Record v{version}  |  Last Updated : {now}\n")
    lines.append(_hr())

    # ── IDENTITY ──────────────────────────────────────────────────────────────
    lines.append(_section("1. Patient Identity"))
    lines.append(_val("Name", f"{g('first_name')} {g('last_name')}"))
    lines.append(_val("Gender", g("gender")))
    lines.append(_val("Date of Birth", g("dob")))
    lines.append(_val("Race / Ethnicity", g("race")))
    lines.append(_val("Address", g("address")))
    lines.append(_val("Phone", g("telecom")))
    lines.append(_val("Marital Status", g("maritalStatus")))
    lines.append(_val("Height", g("height")))
    lines.append(_val("Weight", g("weight")))
    comm = nested("communication")
    lines.append(_val("Primary Language", comm.get("language", "(not recorded)")))

    # ── INSURANCE ─────────────────────────────────────────────────────────────
    lines.append(_section("2. Insurance / Payer"))
    payer = nested("payer")
    lines.append(_val("Payer", payer.get("payer_name", "(not recorded)")))
    lines.append(_val("Provider Abbrev", payer.get("provider_abbreviation", "(not recorded)")))
    lines.append(_val("Provider Policy URL", payer.get("provider_policy_url", "(not recorded)")))
    lines.append(_val("Plan", payer.get("plan_name", "(not recorded)")))
    lines.append(_val("Plan Type", payer.get("plan_type", "(not recorded)")))
    lines.append(_val("Plan ID", payer.get("plan_id", "(not recorded)")))
    lines.append(_val("Plan Policy URL", payer.get("plan_policy_url", "(not recorded)")))
    lines.append(_val("Member ID", payer.get("member_id", "(not recorded)")))
    lines.append(_val("Policy #", payer.get("policy_number", "(not recorded)")))
    lines.append(_val("Effective Date", payer.get("effective_date", "(not recorded)")))
    lines.append(_val("Copay", payer.get("copay_amount", "(not recorded)")))
    lines.append(_val("Deductible", payer.get("deductible_amount", "(not recorded)")))

    # ── PROVIDER ──────────────────────────────────────────────────────────────
    lines.append(_section("3. Care Provider"))
    prov = nested("provider")
    lines.append(_val("GP", prov.get("generalPractitioner", "(not recorded)")))
    lines.append(_val("NPI", prov.get("formatted_npi", "(not recorded)")))
    lines.append(_val("Managing Org", prov.get("managingOrganization", "(not recorded)")))
    contact = nested("contact")
    lines.append(_val("Emergency Contact", f"{contact.get('name', '?')} ({contact.get('relationship', '?')}) — {contact.get('telecom', '?')}"))

    # ── PROCEDURE / PA REQUEST ────────────────────────────────────────────────
    lines.append(_section("4. Procedure & PA Request"))
    lines.append(_val("Requested Procedure", g("procedure_requested")))
    lines.append(_val("Expected Date", g("expected_procedure_date")))
    fac = nested("procedure_facility")
    if fac:
        lines.append(_val("Facility", f"{fac.get('facility_name', '?')}, {fac.get('city', '?')}, {fac.get('state', '?')}"))
        lines.append(_val("Department", fac.get("department", "(not recorded)")))
    pa = nested("pa_request")
    if pa:
        lines.append(_val("PA Requesting Provider", pa.get("requesting_provider", "(not recorded)")))
        lines.append(_val("PA Urgency", pa.get("urgency_level", "(not recorded)")))
        lines.append(_val("PA Justification", pa.get("clinical_justification", "(not recorded)")))
        lines.append(_val("Prior Treatments", pa.get("previous_treatments", "(not recorded)")))

    # ── CURRENT VITALS ────────────────────────────────────────────────────────
    lines.append(_section("5. Current Vital Signs"))
    vs = p.get("vital_signs_current") or {}
    if vs:
        lines.append(_val("Recorded Date", vs.get("recorded_date")))
        lines.append(_val("Blood Pressure", vs.get("blood_pressure")))
        lines.append(_val("Heart Rate", vs.get("heart_rate")))
        lines.append(_val("BMI", vs.get("bmi")))
        lines.append(_val("O2 Saturation", vs.get("oxygen_saturation")))
        lines.append(_val("Temperature", vs.get("temperature")))
        lines.append(_val("Respiratory Rate", vs.get("respiratory_rate")))
        lines.append(_val("Blood Sugar (Fasting)", vs.get("blood_sugar_fasting")))
        lines.append(_val("Blood Sugar (Post-meal)", vs.get("blood_sugar_postprandial")))
    else:
        lines.append("  (Vital signs not recorded)\n")

    # ── SOCIAL HISTORY ────────────────────────────────────────────────────────
    lines.append(_section("6. Social History"))
    sh = p.get("social_history") or {}
    if sh:
        lines.append(_val("Tobacco Use", sh.get("tobacco_use")))
        lines.append(_val("Tobacco Frequency", sh.get("tobacco_frequency")))
        lines.append(_val("Alcohol Use", sh.get("alcohol_use")))
        lines.append(_val("Alcohol Frequency", sh.get("alcohol_frequency")))
        lines.append(_val("Illicit Drug Use", sh.get("illicit_drug_use")))
        lines.append(_val("Substance History", sh.get("substance_history")))
        lines.append(_val("Exercise Habits", sh.get("exercise_habits")))
        lines.append(_val("Diet Notes", sh.get("diet_notes")))
        lines.append(_val("Last Medical Visit", sh.get("last_medical_visit")))
        lines.append(_val("Last Visit Reason", sh.get("last_visit_reason")))
        if sh.get("missed_appointment"):
            lines.append(_val("Missed Appointment", f"YES — {sh.get('missed_appointment_reason', 'reason unknown')}"))
        elif sh.get("missed_appointment") is False:
            lines.append(_val("Missed Appointment", "No"))
        if sh.get("early_visit_reason"):
            lines.append(_val("Early Visit Reason", sh.get("early_visit_reason")))
        lines.append(_val("Mental Health History", sh.get("mental_health_history")))
        lines.append(_val("Mental Health (Current)", sh.get("mental_health_current")))
        lines.append(_val("Family History", sh.get("family_history_relevant")))
    else:
        lines.append("  (Social history not recorded)\n")

    # ── GENDER-SPECIFIC ───────────────────────────────────────────────────────
    gsh = g("gender_specific_history", None)
    if gsh:
        lines.append(_section("7. Gender-Specific History"))
        lines.append(f"  {gsh}\n")

    # ── ENCOUNTERS ────────────────────────────────────────────────────────────
    lines.append(_section("8. Clinical Encounters"))
    encounters = p.get("encounters") or []
    if encounters:
        for i, enc in enumerate(encounters, 1):
            lines.append(f"  Encounter {i}: {enc.get('encounter_date', '?')} — {enc.get('encounter_type', '?')}\n")
            lines.append(_val("Purpose", enc.get("purpose_of_visit"), indent=4))
            lines.append(_val("Provider", enc.get("provider"), indent=4))
            lines.append(_val("Facility", enc.get("facility"), indent=4))
            lines.append(_val("Chief Complaint", enc.get("chief_complaint"), indent=4))
            enc_vs = enc.get("vital_signs") or {}
            if enc_vs:
                lines.append(f"    Vitals: BP={enc_vs.get('blood_pressure', '?')}  HR={enc_vs.get('heart_rate', '?')}  O2={enc_vs.get('oxygen_saturation', '?')}  BMI={enc_vs.get('bmi', '?')}\n")
            if enc.get("doctor_note"):
                lines.append(f"    Doctor Note (SOAP):\n")
                for note_line in enc["doctor_note"].splitlines()[:8]:  # limit to 8 lines for brevity
                    lines.append(f"      {note_line}\n")
            if enc.get("care_team"):
                lines.append(f"    Care Team: {', '.join(enc['care_team'])}\n")
            if enc.get("procedures_performed"):
                lines.append(f"    Procedures: {', '.join(enc['procedures_performed'])}\n")
            lines.append("\n")
    else:
        lines.append("  (No encounters recorded)\n")

    # ── IMAGES ────────────────────────────────────────────────────────────────
    lines.append(_section("9. Imaging Studies"))
    images = p.get("images") or []
    if images:
        for i, img in enumerate(images, 1):
            lines.append(f"  {img.get('date', '?')} — {img.get('type', '?')}\n")
            lines.append(_val("Provider", img.get("provider"), indent=4))
            lines.append(_val("Facility", img.get("facility"), indent=4))
            lines.append(_val("Findings", img.get("findings"), indent=4))
            lines.append("\n")
    else:
        lines.append("  (No imaging studies recorded)\n")

    # ── REPORTS ───────────────────────────────────────────────────────────────
    lines.append(_section("10. Laboratory & Pathology Reports"))
    reports = p.get("reports") or []
    if reports:
        for i, rep in enumerate(reports, 1):
            lines.append(f"  {rep.get('date', '?')} — {rep.get('type', '?')}\n")
            lines.append(_val("Provider", rep.get("provider"), indent=4))
            lines.append(_val("Results", rep.get("results"), indent=4))
            if rep.get("notes"):
                lines.append(_val("Notes", rep.get("notes"), indent=4))
            lines.append("\n")
    else:
        lines.append("  (No reports recorded)\n")

    # ── PROCEDURES ────────────────────────────────────────────────────────────
    lines.append(_section("11. Prior Clinical Procedures"))
    procedures = p.get("procedures") or []
    if procedures:
        for i, proc in enumerate(procedures, 1):
            lines.append(f"  {proc.get('date', '?')} — {proc.get('name', '?')}\n")
            lines.append(_val("Provider", proc.get("provider"), indent=4))
            lines.append(_val("Facility", proc.get("facility"), indent=4))
            lines.append(_val("Reason", proc.get("reason"), indent=4))
            if proc.get("notes"):
                lines.append(_val("Notes", proc.get("notes"), indent=4))
            lines.append("\n")
    else:
        lines.append("  (No prior procedures recorded)\n")

    # ── MEDICATIONS ───────────────────────────────────────────────────────────
    lines.append(_section("12. Medications"))
    meds = p.get("medications") or []
    if meds:
        for m in meds:
            lines.append(f"  [{m.get('status', '?').upper()}] {m.get('brand', '?')} ({m.get('generic_name', '?')}) — {m.get('dosage', '?')}\n")
            lines.append(f"    Qty: {m.get('qty', '?')} | Rx by: {m.get('prescribed_by', '?')} | Reason: {m.get('reason', '?')}\n")
            lines.append(f"    Period: {m.get('start_date', '?')} → {m.get('end_date', 'ongoing')}\n")
    else:
        lines.append("  (No medications recorded)\n")

    # ── ALLERGIES ─────────────────────────────────────────────────────────────
    lines.append(_section("13. Allergies"))
    allergies = p.get("allergies") or []
    if allergies:
        for a in allergies:
            lines.append(f"  {a.get('allergen', '?')} ({a.get('allergy_type', '?')}) — {a.get('reaction', '?')} — Severity: {a.get('severity', '?')}\n")
            lines.append(f"    Onset: {a.get('onset_date', 'Unknown')}\n")
    else:
        lines.append("  NKDA (No Known Drug Allergies)\n")

    # ── VACCINATIONS ──────────────────────────────────────────────────────────
    lines.append(_section("14. Immunization Record"))
    vax = p.get("vaccinations") or []
    if vax:
        for v in vax:
            lines.append(f"  {v.get('vaccine_name', '?')} ({v.get('vaccine_type', '?')}) — Dose {v.get('dose_number', '?')}\n")
            lines.append(f"    Date: {v.get('date_administered', '?')} | By: {v.get('administered_by', '?')} | Reason: {v.get('reason', '?')}\n")
    else:
        lines.append("  (No vaccination records)\n")

    # ── THERAPIES ─────────────────────────────────────────────────────────────
    lines.append(_section("15. Therapies & Rehabilitation"))
    therapies = p.get("therapies") or []
    if therapies:
        for t in therapies:
            lines.append(f"  [{t.get('status', '?').upper()}] {t.get('therapy_type', '?')} — {t.get('frequency', '?')}\n")
            lines.append(f"    CPT: {t.get('cpt_code', '?')} — {t.get('cpt_description', '?')}\n")
            lines.append(f"    ICD-10: {', '.join(t.get('icd10_codes', []) or [])}\n")
            lines.append(f"    Provider: {t.get('provider', '?')} | Facility: {t.get('facility', '?')}\n")
            lines.append(f"    Period: {t.get('start_date', '?')} → {t.get('end_date', 'ongoing')}\n")
            lines.append(f"    Reason: {t.get('reason', '?')}\n")
            if t.get("notes"):
                lines.append(f"    Notes: {t.get('notes')}\n")
    else:
        lines.append("  (No therapy records)\n")

    # ── BEHAVIORAL NOTES ──────────────────────────────────────────────────────
    bn = g("behavioral_notes", None)
    if bn:
        lines.append(_section("16. Behavioral Notes"))
        lines.append(f"  {bn}\n")

    # ── BIO NARRATIVE ─────────────────────────────────────────────────────────
    bio = g("bio_narrative", None)
    if bio:
        lines.append(_section("17. Bio Narrative"))
        for bio_line in bio.splitlines():
            lines.append(f"  {bio_line}\n")

    # ── DOCUMENT INDEX ────────────────────────────────────────────────────────
    lines.append(_section("18. Document Index (This Version)"))
    if docs_generated:
        for doc_name in docs_generated:
            lines.append(f"  • {doc_name}\n")
    else:
        lines.append("  (No documents generated this run)\n")

    # ── FEEDBACK LOG ──────────────────────────────────────────────────────────
    if feedback and feedback.strip():
        lines.append(_section("19. Generation Feedback Log"))
        lines.append(f"  [{now}] v{version}\n")
        lines.append(f"  {feedback.strip()}\n")

    lines.append("\n" + _hr())

    # Write file
    content = "".join(lines)
    try:
        # Append feedback log to existing file if possible, else overwrite
        existing = ""
        prev_feedback = ""
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                existing = f.read()
            # Extract previous feedback log section
            feedback_marker = "─" * 70 + "\n  19. GENERATION FEEDBACK LOG\n"
            if feedback_marker.upper() in existing.upper():
                idx = existing.upper().find(feedback_marker.upper())
                prev_feedback = existing[idx:]

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
            if prev_feedback and feedback and feedback.strip():
                # Append historical feedback after current log
                f.write("\n  ── Earlier Feedback ──\n")
                f.write(prev_feedback)

    except Exception as e:
        print(f"      ⚠️  Could not write patient record: {e}")

    return out_path
