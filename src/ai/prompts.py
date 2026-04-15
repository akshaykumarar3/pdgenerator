"""
AI Prompts Configuration

This file contains all AI prompts and instructions used throughout the application.
Edit these prompts carefully to modify AI behavior.

⚠️ IMPORTANT GUIDELINES FOR EDITING:
1. Do NOT use any report start/end markers. Output clean, realistic clinical documents only.
2. Keep field names consistent (e.g., PATIENT_ID, MRN, DOB)
3. Test changes thoroughly - incorrect prompts can break document validation
4. Add new instructions at the end of relevant sections
5. Use f-string placeholders (e.g., {case_details['procedure']}) for dynamic values
"""

import datetime

# ============================================================================
# SYSTEM PROMPT - Core AI Behavior
# ============================================================================
# This defines the AI's role and core rules for all operations.
# EDIT WITH CAUTION: Changes here affect all AI responses.

SYSTEM_PROMPT = """You are an expert healthcare data generator.
Your task: generate realistic, diverse clinical personas and medical documents based on clinical use cases.

=== Core Rules ===
1. Generate data that is FHIR-compliant and visually realistic.
2. **Inference**: If CPT/procedure is not provided, infer the most clinically appropriate code.
3. Suggest CPTs intelligently.
4. Output valid, JSON-structured data.
5. **No SQL**: Do not generate SQL. Focus on the Object Model.
6. **Medical Coding**: Use REAL, medically appropriate ICD-10 CM codes that support medical necessity for the requested CPT procedure.
7. **Insurance Standardization**: The `payer` section MUST match the `patient_state.insurance` details (payer_name, plan_name, plan_type, payer_id). If patient_state includes provider_abbreviation or policy URLs, include them exactly. Do NOT invent new payer info.
8. **No Coverage/Sufficiency Judgments**: Do NOT include explicit approval/denial recommendations or judgments about sufficiency of evidence (e.g., "not indicated", "not medically necessary", "lacks rationale", "meets criteria", "insufficient evidence"). Present clinical facts and findings only.
9. **Avoid the Word "Justification"**: Do not use the word "justification" in narrative text. Use factual clinical findings and prior treatment history instead.
10. **Positive Evidence Emphasis**: Clinical narratives should emphasize positive, factual evidence (symptoms, findings, prior treatments, objective data) that supports the requested procedure without stating sufficiency or correctness.
11. **No Outcome Guarantees**: Do not promise or imply the procedure will "fix" or "resolve" the condition. Describe goals and clinical reasoning grounded in documented findings.
12. **USA Standards Mandate**: EVERYTHING must use USA formatting and measurement systems. 
    - Dates must be MM-DD-YYYY. 
    - Numbering must use US format (e.g., 1,000 for thousands, 1.5 for decimals). 
    - Height must be in feet and inches (e.g., '5 ft 10 in'). Weight must be in pounds (lbs). 
    - Temperature must be in Fahrenheit (°F). 
    - Standard US customary units must be applied for all general sizing and measurements, but standard medical scores (e.g. BMI, lab units) should be preserved as numbers. Do NOT use kg, cm, or Celsius.

=== MANDATORY PERSONA SECTIONS ===
Every generated patient persona MUST include ALL of the following. No empty lists allowed for new patients:

A. **Medications** (5-10 entries):
   - Mix of current, past, and ongoing medications appropriate for the patient's conditions
   - Include brand name, generic + dosage, qty, prescribing physician, status, start/end dates, clinical reason
   - Medications must align with ICD-10 diagnoses

B. **Allergies** (1-5 entries):
   - Include drug, food, and/or environmental allergies as clinically appropriate
   - For each: allergen, allergy_type (Drug/Food/Environmental/Latex/Other), reaction, severity, onset_date

C. **Vaccinations** (3-10 entries — full history):
   - Include routine + condition-specific vaccines
   - For each: vaccine_name, vaccine_type, dose_number, reason, date_administered, administered_by

D. **Therapies** (0-4 entries — with procedure codes):
   - Supported types: Physical, Occupational, Mental Health / Psychotherapy, Medication Management (Psychiatry),
     Cognitive-Behavioral (CBT), Dialectical Behavior (DBT), EMDR, Group Therapy,
     Speech, Respiratory, Cardiac Rehab, Pulmonary Rehab, Aquatic, Other
   - EACH therapy MUST include: therapy_type, provider, provider_npi, facility, start_date, end_date,
     frequency, status (Active/Completed/Discontinued), reason, notes,
     cpt_code (CPT / HCPCS / CDT), cpt_description, icd10_codes (list of supporting ICD-10 codes)

E. **Social History** (SocialHistory object — some fields may be null at random):
   - tobacco_use, tobacco_frequency, alcohol_use, alcohol_frequency, illicit_drug_use, substance_history
   - last_medical_visit (date), last_visit_reason
   - missed_appointment (bool), missed_appointment_reason, early_visit_reason
   - mental_health_history, mental_health_current (PHQ-9/GAD-7 result if applicable)
   - exercise_habits, diet_notes, family_history_relevant
   - RULE: Fields may be null for some patients (random), UNLESS feedback explicitly specifies them

F. **Encounters** (2-5 chronological encounters — ALL required):
   - Each encounter MUST have: encounter_date, encounter_type, purpose_of_visit, provider, provider_npi,
     facility, chief_complaint, doctor_note (full SOAP note), vital_signs (or null),
     observations, procedures_performed (with CPT codes), diagnoses (with ICD-10),
     medications_prescribed, care_team, progress_notes, follow_up_instructions
   - Encounters MUST be ordered chronologically and match the temporal timeline
   - Encounter types: Office Visit, ER Visit, Telehealth, Follow-up, Specialist Consult, Pre-op Evaluation
   - doctor_note MUST include: HPI, Review of Systems, Physical Exam findings, Assessment, Plan

G. **Vital Signs** (VitalSigns object — fields may be null for some patients):
   - blood_pressure, heart_rate, blood_sugar_fasting, blood_sugar_postprandial, bmi, oxygen_saturation,
     temperature, respiratory_rate
   - RULE: Some fields may be null at random for realism (e.g., blood sugar not recorded if not diabetic)
   - Record current vitals in vital_signs_current AND within each encounter's vital_signs

H. **Gender-Specific History** (gender_specific_history — text or null):
   - Female: gravida/para, last Pap smear, mammogram, OB/GYN history
   - Male: PSA, prostate screening, urologic history
   - Other/null: if not clinically relevant

I. **Behavioral Notes** (free text):
   - Concise paragraph: medication adherence, lifestyle, mental health flags, substance use history

J. **Medical Biography & History (bio_narrative - MANDATORY)**:
   - Generate a comprehensive, multi-paragraph longitudinal medical history (300-500 words).
   - This section is the narrative foundation of the patient persona.
   - Include:
     * Detailed HPI (History of Present Illness) leading to the requested procedure.
     * Comprehensive Social History (lifestyle, occupation, support system).
     * Detailed Family History relevant to the current condition.
     * Longitudinal timeline of symptoms and previous treatments.
     * Clinical rationale for the current referral/request.
   - **NEVER leave this section blank**. If source data is limited, synthesize a clinically plausible, high-quality narrative that stays consistent with the persona, encounters, diagnoses, and requested procedure.
   - USE PLAIN TEXT. NO MARKDOWN. NO BOLDING.

=== PERSONA DOCUMENT AS SOURCE OF TRUTH ===
**CRITICAL**: The patient_persona document is the SINGLE SOURCE OF TRUTH. All generated reports MUST:
- Reference ONLY the CPT codes, ICD-10 codes, and procedures defined in the persona.
- Maintain 100% consistency with persona demographics, medical history, and clinical details.
- NEVER introduce new conditions, procedures, or codes not established in the persona.
- Reference medications, allergies, and therapy history where clinically relevant.
- Include per-document DOCTOR NOTES and PROGRESS NOTES based on the encounter records.

=== CRITICAL PROJECT CONSTRAINTS ===
A. **Data Density (DYNAMIC)**:
   - Generate documents based on CLINICAL COMPLEXITY, NOT a fixed number.
   - Simple cases: 3-4 documents. Moderate: 5-6. Complex: 7-10.
   - No filler documents.
B. **Clinical Status**:
   - Target Procedure must be 'requested'. Historical Procedures 'completed'.
C. **NO AI RESIDUE**: No "[Redacted]" or "Jane Doe". Use Pop Culture character names.
D. **NAMING CONVENTION**: Use names from: Friends, Marvel, Star Wars, etc.
E. **INSURANCE**: MUST match `patient_state.insurance` (payer_name, plan_name, plan_type). Include provider_abbreviation and policy URLs if provided.
F. **GEOGRAPHIC CONSTRAINT (MANDATORY)**:
   - ALL patients MUST be in **Texas, USA**.
   - Addresses: real TX cities (Houston, Dallas, San Antonio, Austin, etc.).
   - Facilities: real TX hospitals (Houston Methodist, UT Southwestern, etc.).
   - State code: ALWAYS "TX".
"""


# ============================================================================
# CLINICAL DATA GENERATION PROMPT - Main Document Generation
# ============================================================================
# This is the primary prompt for generating patient personas and clinical documents.
# 
# KEY SECTIONS TO CUSTOMIZE:
# - Data Density: Adjust minimum document count (currently 5)
# - Timeline Logic: Modify how past/future dates are handled
# - Document Formatting: Critical for validation - do not change markers
# - Persona Requirements: Add/remove required patient fields

def _build_clinical_logic_instruction(case_details: dict) -> str:
    """
    Build the Clinical Logic Application instruction (prompt instruction #2).

    For approval outcomes: returns a standard strong-evidence directive.
    For denial/rejection outcomes: samples multi-dimensional gap archetypes
    and returns a sophisticated injection block designed to embed nuanced,
    cross-referential inconsistencies rather than obvious surface-level gaps.
    """
    import re as _re
    outcome = str(case_details.get("outcome", "") or "")
    if _re.search(r"(reject|rejection|deny|denial|low\s+probability)", outcome, _re.IGNORECASE):
        return get_rejection_gap_instruction(case_details)
    return (
        "If Target is Approval or High Probability → ENSURE strong supporting evidence exists. "
        "Generate comprehensive clinical documentation with clear medical necessity, detailed "
        "diagnostic workup, and explicit treatment rationale. Every finding must positively "
        "corroborate the requested procedure."
    )

def get_clinical_data_prompt(case_details: dict, patient_state: dict, document_plan: dict, user_feedback: str = "",
                             history_context: str = "", existing_persona: dict = None) -> str:
    """
    Generates the main prompt for clinical data generation.
    
    Args:
        case_details: Dict with 'procedure', 'outcome', 'details'
        patient_state: Dict from state_manager.py containing deterministic identifiers & blanks
        document_plan: Dict containing the document templates to fill
        user_feedback: Optional user corrections/instructions
        history_context: Previous interaction history
        existing_persona: Optional existing patient persona dictionary
    
    Returns:
        Complete prompt string
    """
    
    import json
    import random
    state_str = json.dumps(patient_state, indent=2)
    plan_str = json.dumps(document_plan, indent=2)
    feedback_instruction = get_feedback_instruction(user_feedback)
    
    # 1. Handle Random Character Universe (Only for new patients)
    diversity_instruction = ""
    if not existing_persona:
        universe = random.choice(CHARACTER_UNIVERSES)
        diversity_instruction = f"""
    **PERSONA DIVERSITY INSTRUCTION**:
    To ensure demographic and naming diversity, loosely base the patient's name, personality traits (in behavioral notes), and general background on a character from the fictional universe: "{universe}". 
    DO NOT mention the universe or character name directly. Just use it as inspiration for realism and variety.
    """

    # 2. Handle Existing Persona Constraint
    existing_constraint_str = ""
    if existing_persona:
        existing_constraint_str = get_existing_patient_constraint(existing_persona, case_details)

    return f"""
    **CLINICAL SCENARIO Requirements (IMMUTABLE Source of Truth):**
    - Procedure: {case_details['procedure']}
    - Target Outcome: {case_details['outcome']}
    - Clinical Context: {case_details['details']}
    
    {diversity_instruction}
    
    **PATIENT STATE LAYER (DETERMINISTIC IDENTIFIERS):**
    You MUST adhere strictly to the generated state identifiers:
    ```json
    {state_str}
    ```
    {existing_constraint_str}

    
    **DOCUMENT PLAN (TEMPLATES TO FILL):**
    The following templates must be populated. The keys denote the expected JSON structures:
    ```json
    {plan_str}
    ```
    
    **PAST HISTORY (CONTEXT):**
    {history_context if history_context else "No prior history available."}

    {feedback_instruction}

    **INSTRUCTIONS:**
    1. **Identity & Consistency**:
       - Maintain strict patient identity if provided.
       - Ensure all documents match the patient demographics.
    2. **Clinical Logic Application**:
       {_build_clinical_logic_instruction(case_details)}
    3. **Clinical Status**:
       - The *Target Procedure* ({case_details['procedure']}) Status: 'requested'.
       - All *historical* procedures must be implied as 'completed'.
    4. **Medical Coding Requirements (CRITICAL - PERSONA IS SOURCE OF TRUTH)**:
       - **CPT Code (MANDATORY IN PERSONA)**: The target procedure MUST be specified with its CPT code (e.g., "CPT [CODE] - [DESCRIPTION]").
       - **ICD-10 Codes (MANDATORY IN PERSONA)**: Generate REAL ICD-10-CM diagnosis codes that clinically support the medical necessity of the requested procedure.
       - **Persona Must Include**:
         - `target_cpt_code`: The exact CPT code for the requested procedure.
         - `target_cpt_description`: Full description of the procedure.
         - `primary_diagnosis_codes`: List of primary ICD-10 codes justifying the procedure.
         - `secondary_diagnosis_codes`: List of secondary/supporting ICD-10 codes.
         - `procedure_history`: List of relevant past procedures with their CPT codes.
       - **Medical Necessity**: ICD-10 codes must be medically appropriate and commonly used to justify the CPT procedure.
       - **Code Format**: ICD-10 codes should follow the format (e.g., "I25.10" for atherosclerotic heart disease, "R07.9" for chest pain).
       - **STRICT ALIGNMENT**: ALL reports MUST reference ONLY the codes defined in the persona. NO new codes may be introduced in reports.
       - **CONSISTENCY RULE**: Any ICD-10 code referenced in the body of a clinical document or PA request MUST identically match a code listed in the `supporting_diagnoses` array and persona's diagnosis list.
       - **FACILITY CONSISTENCY**: The `procedure_facility.facility_name` MUST be populated identically across ALL document headers, procedure plans, and PA location fields without variation.
    5. **Data Density (DYNAMIC - Based on Clinical Complexity)**:
       - **DO NOT default to a fixed number of documents.**
       - Assess the clinical complexity and generate an APPROPRIATE number:
         - **Simple procedures** (e.g., routine imaging, minor outpatient): 3-4 documents.
         - **Moderate complexity** (e.g., surgical procedures, multiple conditions): 5-6 documents.
         - **High complexity** (e.g., chronic disease, multiple specialists, prior authorizations needed): 7-10 documents.
       - **Each document must provide UNIQUE clinical value**. No filler or redundant documents.
       - **Document types to consider**: Consult Notes, Lab Reports, Imaging Reports, Procedure Notes, Discharge Summaries, Specialist Notes, Physical Therapy Notes, Prior Authorization Requests, Referral Letters, Medication Lists, Progress Notes.
     6. **Document Generation (CRITICAL Rules)**:
        - Generate `documents` list with rich, detailed content.
        - **NO START/END MARKERS**: Do NOT use '--- REPORT START ---' or '--- REPORT END ---'. Begin documents directly.
        - **REPORT DETAIL REQUIREMENTS**:
          - Each report must contain comprehensive clinical information relevant to its type.
          - Include specific findings, measurements, interpretations, and clinical impressions.
          - Reference the CPT and ICD-10 codes from the persona where clinically appropriate.
          - Include detailed clinical narratives including doctor notes and progress notes.
          - Reference relevant encounters from the patient's encounter history.
        - **DOCUMENT CONTENT INTENSITY (MANDATORY)**:
          - Each document must be **self-contained** for Prior Authorization review: an auditor must understand indication and supporting evidence without opening other files.
          - **Minimum length/detail by section type** (one-line or N/A-style answers are NOT acceptable for core clinical sections):
            * **findings, impression, procedure_description, operative_findings, session_summary, therapist_observations**: At least 2-4 sentences (40-80 words) with specific measurements, dates, or clinical terms where appropriate.
            * **clinical_justification, HPI, assessment, plan, clinical_indication**: Multi-sentence with clear medical necessity and timeline.
            * **procedure_details, study_information**: Fill all sub-fields with realistic values; do not leave empty strings for required keys.
          - **Example — MINIMAL (bad)**: findings: "No acute findings."
          - **Example — INTENSIVE (good)**: findings: "Cardiac CT angiography was performed with contrast. The left main, LAD, circumflex, and right coronary arteries are patent. There is non-obstructive plaque in the mid-LAD (approximately 20% stenosis). Left ventricular size and function are normal. No pericardial effusion. Incidental note: small hepatic cyst in segment VII, stable from prior."
          - For each section in the DOCUMENT PLAN (findings, impression, clinical_history, procedure_description, etc.), provide at least 2-4 sentences with specific clinical detail; avoid one-line answers.
          - **PRE-OP EVALUATION RULE**: If the patient has ANY active therapies listed in their persona, any Pre-Op Evaluation document MUST include a "Concurrent Care Reference" field explicitly noting the active therapy.
          - **LAB/ENCOUNTER MAPPING RULE**: Any lab result events referenced in clinical timelines must either map directly to an existing encounter or be created as a distinct encounter entry.
         - **DOCUMENT OUTPUT FORMAT**:
          For each document template specified in the DOCUMENT PLAN, create a entry in the `documents` list.
          The `content` field MUST contain the fully populated JSON object matching the template structure.
          Do NOT attempt to use markdown or raw text in `content`—it MUST be a structured JSON object.
          The `title_hint` field should match the template's title or logically reflect it.
         - **FEEDBACK-DRIVEN DOCUMENTS (CRITICAL ESCAPE HATCH)**:
           If the USER FEEDBACK mentions missing documents (e.g., "Missing ECG", "No Risk Assessment"), you MUST invent and generate a NEW document for each requested item, even if it is not in the DOCUMENT PLAN. Create a fitting JSON structure for these ad-hoc documents (e.g. `{{\"doc_type\": \"ECG\", \"findings\": \"...\", \"interpretation\": \"...\"}}`) and add them to the `documents` list.
        - **PROHIBITED TITLES**: No "Approval Letters" or "Denial Notices". Only clinical evidence.
        - **TITLES**: MUST be UNIQUE and DESCRIPTIVE (e.g. "Cardiology_Consult", "Echo_Report").
        - **NO MARKDOWN BOLD**: Do not use `**Text**`.
        - **NO TRIPLE QUOTES**: Do not use `'''`.
       - **METADATA**:
          - `service_date`: Must be logically consistent (Historical dates for evidence, recent for request).
          - `facility_name` & `provider_name`: Realistic and consistent.
    7. **PERSONA-REPORT ALIGNMENT (MANDATORY)**:
       - **ZERO DEVIATION POLICY**: All generated reports MUST be in complete alignment with the persona document.
       - All diagnoses mentioned in reports MUST use the ICD-10 codes from the persona.
       - All procedures mentioned MUST use the CPT codes from the persona.
       - Patient demographics, history, and clinical details MUST match the persona exactly.
       - Any clinical findings MUST support the diagnoses listed in the persona.
       - DO NOT introduce any new conditions, procedures, or codes not in the persona.
    7b. **SUPPORTING TESTS MUST REFERENCE TARGET PROCEDURE (CRITICAL)**:
       - When the case involves a target procedure, any **supporting** documents (ECG, stress test, echo, lab panels, etc.) exist to justify that procedure.
       - In each supporting report, **explicitly state** in `clinical_indication`, `findings`, and/or `impression` that the test supports or is in preparation for the target procedure. Example: "Obtained in workup prior to requested procedure;" "Findings support need for procedure to assess clinical status;" "Results support proceeding with scheduled imaging/surgery."
       - Do NOT leave supporting reports as standalone items with no link to the target procedure. The persona PDF and standalone report PDFs must make the clinical link clear so auditors see why each document exists.
       - Every report's `content` JSON must be **fully populated** (no empty sections); the persona's "Clinical Reports & Imaging" section displays this content and must not be blank.
    8. **TEMPORAL CONSISTENCY (CRITICAL - NEW REQUIREMENT)**:
       - **Today's Date**: {datetime.datetime.now().strftime("%m-%d-%Y")}
       - **Expected Procedure Date**: MUST be 7-90 days in the FUTURE from today
       - **Timeline Requirements (IMPORTANT)**:
         * Completed clinical events (encounters, consults, ER visits, doctor notes, imaging, lab/pathology results, prior procedures, vaccinations, vitals recorded) MUST be dated ON or BEFORE today's date.
         * Future-dated "completed" items are NOT allowed.
         * Future dates are allowed ONLY for: expected_procedure_date and scheduling text inside follow_up_instructions / pre-procedure hold instructions (i.e., plans), not as completed encounters/reports.
         * Medical history events: 6 months to 5 years BEFORE today's date
         * Recent encounters/consultations: 1-12 weeks BEFORE today's date
         * Lab results/diagnostic tests: 1-4 weeks BEFORE today's date
         * ALL completed evidence dates must be BEFORE the expected procedure date
       - **Example Timeline**:
         * Today: {datetime.datetime.now().strftime("%m-%d-%Y")}
         * Procedure Date: {(datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%m-%d-%Y")} (example: 30 days in future)
         * Recent Consultation (completed): {(datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%m-%d-%Y")} (example: 7 days before today)
         * Lab Results (completed): {(datetime.datetime.now() - datetime.timedelta(days=12)).strftime("%m-%d-%Y")} (example: 12 days before today)
         * Medical History (completed): {(datetime.datetime.now() - datetime.timedelta(days=600)).strftime("%m-%d-%Y")} (example: ~20 months ago)
    9. **FACILITY LOCATION (CRITICAL - NEW REQUIREMENT)**:
       - **Procedure Facility**: Generate a realistic healthcare facility where the procedure will be performed
       - **Requirements**:
         * Facility MUST be in the SAME STATE as patient's home address
         * Use realistic hospital/clinic names (e.g., "Memorial Hospital", "St. Mary's Medical Center", "[City] Regional Hospital")
         * Include appropriate department for procedure type (e.g., "Cardiology Department", "Surgical Center", "Radiology")
         * Generate valid street address and 5-digit ZIP code matching the city/state
         * Facility should be appropriate for the procedure complexity
       - **Examples**:
         * Patient in Boston, MA → "Massachusetts General Hospital, Cardiology Department, 55 Fruit Street, Boston, MA 02114"
         * Patient in Los Angeles, CA → "Cedars-Sinai Medical Center, Surgical Center, 8700 Beverly Blvd, Los Angeles, CA 90048"
         * Patient in Houston, TX → "Houston Methodist Hospital, Radiology Department, 6565 Fannin Street, Houston, TX 77030"
    10. **PRIOR AUTHORIZATION REQUEST (CRITICAL - NEW REQUIREMENT)**:
       - **PA Request Form**: Generate complete Prior Authorization request details
       - **Required Fields**:
         * `requesting_provider`: Realistic physician name with credentials (e.g., "Dr. Sarah Johnson, MD, FACC")
         * `urgency_level`: "Routine", "Urgent", or "Emergency" (based on clinical scenario)
         * `clinical_justification`: 2-3 sentences explaining medical necessity for the procedure
         * `supporting_diagnoses`: List of ICD-10 codes with descriptions that support the PA request
         * `previous_treatments`: Prior treatments attempted (or "None" if first-line treatment)
         * `expected_outcome`: Expected clinical benefit (e.g., "Improved cardiac function", "Pain relief", "Diagnosis confirmation")
       - **Example PA Request**:
         * Requesting Provider: "Dr. Michael Chen, MD, FACC"
         * Urgency: "Routine"
         * Justification: "Patient presents with persistent symptoms and relevant diagnostic findings. The requested procedure is medically necessary to manage the patient's condition and guide treatment planning."
         * Supporting Diagnoses: ["I25.10 - Atherosclerotic heart disease", "R07.9 - Chest pain, unspecified"]
         * Previous Treatments: "Conservative management with beta-blockers and lifestyle modifications"
         * Expected Outcome: "Definitive diagnosis of coronary perfusion status to guide revascularization decision"
       - **STANDARD LABELS & COMORBIDITIES**:
         * The `urgency_level` MUST use standard labels: "Pre-Service Routine", "Expedited/Urgent", or "Concurrent Review" based on procedure category.
         * The PA `clinical_justification` and risk-benefit analysis MUST explicitly reference at least one relevant comorbidity from the patient's medical history (if present) to justify the clinical pathway.
         * Set `units_requested`: Use "1" for surgical procedures, and calculated session counts (e.g., "12 sessions") for therapies.
    11. **Persona Generation (COMPLETE FHIR-COMPLIANT DATA)**:
       - You MUST populate the `patient_persona` object with ALL fields. **NO NULL VALUES ALLOWED**.
       - **CRITICAL IMPERATIVE**: You MUST rely ONLY on `patient_state` for identifiers, MRN, naming, and demographics. DO NOT CREATE NEW IDENTIFIERS.
       - **Required Fields (ALL MUST BE FILLED)**:
         - `first_name`, `last_name`, `gender`, `dob`, `address`, `telecom`
         - **Biometrics**: `race`, `height` (Must be in feet/inches, e.g., '5 ft 10 in'), `weight` (Must be in pounds, e.g., '180 lbs')
         - `maritalStatus`, `photo` (default placeholder)
         - `communication`, `contact` (Emergency)
         - `provider` (GP), `link` (N/A)
         - **Provider NPI (MANDATORY)**: `provider.formatted_npi`. Format "XXXXXXXXXX" (10 digits). **STRICT RULE**: Every NPI must be assigned ONCE per provider. The same provider across all encounters, therapies, and documents MUST reuse the EXACT SAME NPI. The provider's FULL NAME string must also be identical everywhere it appears. No provider can have two different NPIs; no two providers can share the same NPI.
         - **Clinical Coding (MANDATORY - Must be filled for report alignment)**:
           - `target_cpt_code`: CPT code for the requested procedure
           - `target_cpt_description`: Full procedure description
           - `primary_diagnosis_codes`: List of primary ICD-10 codes
           - `secondary_diagnosis_codes`: List of secondary ICD-10 codes
           - `procedure_history`: List of past relevant procedures
         - **NEW MANDATORY FIELDS (Temporal & Facility)**:
           - `expected_procedure_date`: Future date (MM-DD-YYYY, 7-90 days from today)
           - `procedure_requested`: Full procedure name
           - `procedure_facility`: FacilityDetails object (name, address, city, state, ZIP, department)
           - `pa_request`: PARequestDetails object (all PA form fields)
        - **payer (MANDATORY - MUST MATCH patient_state.insurance)**:
          - `payer_id`, `payer_name`, `plan_name`, `plan_type` MUST match `patient_state.insurance`
          - If present, include `provider_abbreviation`, `provider_policy_url`, `plan_id`, `plan_policy_url`
          - `policy_number`: Format "POL-YYYY-XXXXXX" (year + 6 digits)
          - All other payer fields (deductible, copay, effective_date)
        - **Bio Narrative (PLAIN TEXT)**:
          - Rich multi-paragraph history (Personality, HPI, Social). NO Markdown.
          - MUST reference the diagnosis codes and clinical history established in the persona.
     12. **MEDICATIONS (MANDATORY — min 3 entries)**:
        - ALL medications MUST be realistic and clinically appropriate for the ICD-10 diagnoses.
        - Mix statuses: some 'current', some 'past', some 'ongoing'.
        - **PAST STATUS RULE**: When a medication status is set to "past" with an end date, any narrative reference to that medication in PA or clinical docs must use PAST TENSE and appear under "Previous Treatments" only, never as active or PRN.
        - **HOLD INSTRUCTION RULE**: If a medication requires a pre-procedure hold, dynamically calculate and output specific dates based on the procedure date (e.g., if procedure is Nov 10 and hold is 5 days, explicit text must say "Hold starting Nov 5") rather than generic durations.
        - If user provided medications → use EXACTLY as given. If patient is EXISTING → reproduce from locked constraint.
     13. **ALLERGIES (MANDATORY — min 1 entry)**:
        - Each MUST have: allergen, allergy_type (Drug/Food/Environmental/Latex/Other), reaction, severity, onset_date.
        - Drug allergies should be clinically relevant.
        - If user provided allergies → use EXACTLY as given. If patient is EXISTING → reproduce from locked constraint.
     14. **VACCINATIONS (MANDATORY — min 4 entries, full history)**:
        - Include standard adult vaccines + condition-specific vaccines.
        - Each MUST have: vaccine_name, vaccine_type (Inactivated/mRNA/Live-attenuated/Toxoid/Subunit/Viral vector/Other), date_administered, administered_by, dose_number, reason.
        - Reason options: 'Routine Immunization', 'Travel', 'Occupational', 'Post-exposure Prophylaxis', 'Catch-up'.
        - If user provided vaccinations → use EXACTLY as given. If patient is EXISTING → reproduce from locked constraint.
     15. **THERAPIES (Generate 0-4 entries based on clinical profile, with procedure codes)**:
        - Supported types: Physical, Occupational, Mental Health / Psychotherapy, Medication Management (Psychiatry),
          CBT, DBT, EMDR, Group Therapy, Speech, Respiratory, Cardiac Rehab, Pulmonary Rehab, Aquatic, Other.
        - Each MUST have: therapy_type, provider, provider_npi, facility, start_date, end_date, frequency,
          status (Active/Completed/Discontinued), reason, notes,
          cpt_code (CPT/HCPCS/CDT code e.g. '97110', '90834', 'H0035', 'G0463'),
          cpt_description (full code description),
          icd10_codes (list of supporting ICD-10 codes).
        - **THERAPY PLAN MATCHING**: Any CPT codes listed in therapy plans (e.g., PT/OT sessions) within clinical notes MUST strictly correspond to the codes populated in the patient persona's `therapies` section.
        - If user provided therapies → use EXACTLY as given. If patient is EXISTING → reproduce from locked constraint.
     16. **BEHAVIORAL NOTES (MANDATORY)**:
        - A concise paragraph: medication adherence, lifestyle habits (diet, exercise, smoking, alcohol), mental health flags, substance use history.
        - Must be consistent with social_history fields.
        - If patient is EXISTING → reproduce behavioral_notes verbatim.
     17. **SOCIAL HISTORY (SocialHistory object — MANDATORY)**:
        - Generate social_history object with all fields. Some may be null at random (realistic variation).
        - tobacco_use, tobacco_frequency, alcohol_use, alcohol_frequency, illicit_drug_use, substance_history
        - last_medical_visit (MM-DD-YYYY), last_visit_reason
        - missed_appointment (true/false/null), missed_appointment_reason, early_visit_reason
        - mental_health_history, mental_health_current (PHQ-9/GAD-7 if applicable, else null)
        - exercise_habits, diet_notes, family_history_relevant
        - RULE: If feedback adds or removes a field, override the random null with the specified value.
     18. **VITAL SIGNS (vital_signs_current — MANDATORY)**:
        - Generate vital_signs_current. Some sub-fields may be null for realism.
        - Required: recorded_date. Optional (randomly null): blood_pressure, heart_rate, blood_sugar_fasting,
          blood_sugar_postprandial, bmi, oxygen_saturation, temperature, respiratory_rate.
        - Clinically consistent (e.g., blood sugar readings present for diabetic patients).
     19. **ENCOUNTERS (2-5 chronological encounters — MANDATORY)**:
        - Generate encounters list ordered from oldest to most recent.
        - Each encounter MUST have:
          * encounter_date (MM-DD-YYYY, must respect temporal timeline)
          * encounter_type: Office Visit / ER Visit / Telehealth / Follow-up / Specialist Consult / Pre-op Evaluation
          * purpose_of_visit: 1-2 sentence description of why the patient came in
          * provider + provider_npi, facility
          * chief_complaint: patient's own words
          * doctor_note: Full SOAP note (Subjective, Objective, Assessment, Plan) — 2-4 paragraphs
          * vital_signs (VitalSigns object or null)
          * observations: list of clinical observations
          * procedures_performed: ['CPT 99213 - E&M Office Visit Level 3', '93000 - 12-lead ECG']
          * diagnoses: ['I25.10 - Atherosclerotic heart disease']
          * medications_prescribed: list of medications ordered
          * care_team: list of all providers involved
          * progress_notes: clinical progress relative to prior visits
          * follow_up_instructions: instructions given to patient
        - LAST encounter should be the most recent pre-procedure evaluation.
        - **CONSISTENCY**: The encounter list in the clinical summary MUST be generated from the exact same source array as the persona master record; no encounter should exist in one document that doesn't exist in the other.
        - If patient is EXISTING → reproduce prior encounters exactly, and APPEND new ones as needed.
     20. **IMAGES (0-4 chronological imaging studies)**:
        - Generate images list. Each MUST have: type, date, provider, facility, findings.
        - Relate to the chief complaint or history if present.
        - If patient is EXISTING → reproduce prior images exactly, and APPEND new ones as needed.
     21. **REPORTS (0-4 chronological lab/pathology reports)**:
        - Generate reports list. Each MUST have: type, date, provider, results, notes.
        - If patient is EXISTING → reproduce prior reports exactly, and APPEND new ones as needed.
     22. **PROCEDURES (0-4 chronological prior clinical procedures)**:
        - Generate procedures list. Each MUST have: name, date, provider, facility, reason, notes.
        - If patient is EXISTING → reproduce prior procedures exactly, and APPEND new ones as needed.
      23. **GENDER-SPECIFIC HISTORY & FLAGS**:
        - Female patients: Include OB/GYN history (gravida/para), last Pap smear date, mammogram date.
        - Male patients: Include PSA level (if age-appropriate), prostate screening history, urologic history.
        - **GI CASES**: For GI procedures, set `has_fit_fobt_result` explicitly to True/False. The FIT/FOBT result flag must be consistently reflected as either positive or negative across all GI-related consults, lab reports, and PA forms.
        - If not clinically applicable: set to null.
      24. **DOCUMENT JSON STRUCTURE (MANDATORY)**:
        - Each document's `content` must be a valid JSON object.
        - Do not include raw text headers or demographics in the `content` JSON; these are handled by the system.
        - Focus solely on populating the clinical sections defined in the DOCUMENT PLAN.
     25. **PA APPROVAL STRATEGY**:
        - If the expected outcome ({case_details['outcome']}) indicates "Approval" or "Likelihood", OR if user feedback contains "PA APPROVAL OPTIMIZATION":
          → Generate all clinical documents with the STRONGEST possible medical justification.
          → Include comprehensive clinical evidence, detailed findings, thorough rationale.
     26. **OUTPUT STRUCTURE (MANDATORY - NO EXCEPTIONS)**:
        - You MUST return a `ClinicalDataPayload` JSON object with ALL three top-level fields: `patient_persona`, `documents`, and `changes_summary`.
        - **patient_persona** is REQUIRED even when user feedback asks for more reports, observations, or clinical timeline. Adding documents never means omitting the persona.
        - If feedback requests "more supporting reports", "more observations", or "clinical timeline" — ADD those to `documents` and enrich `encounters`/`bio_narrative`, but ALWAYS include the complete `patient_persona` object.
     27. **Output**: Return the `ClinicalDataPayload` JSON with patient_persona, documents, and changes_summary.
     """

# ============================================================================
# IDENTITY CONSTRAINTS - Patient Identity Generation Rules
# ============================================================================
# Controls how patient identities are created (new) or maintained (existing).

def get_existing_patient_constraint(existing_persona: dict, case_details: dict) -> str:
    """
    Generates constraint for maintaining existing patient identity.
    
    WHEN TO USE: Patient already exists, updating their records.
    EFFECT: Locks ALL persona fields including medications/allergies/vaccinations/therapies.
    """
    # Build locked medication list
    med_lock = ""
    meds = existing_persona.get('medications', [])
    if meds:
        med_lines = []
        for m in meds:
            if isinstance(m, dict):
                med_lines.append(f"      - [{m.get('status','').upper()}] {m.get('brand','')} ({m.get('generic_name','')}) {m.get('dosage','')} | By: {m.get('prescribed_by','')} | Reason: {m.get('reason','')}")
        med_lock = "\n    - Medications (LOCK EXACTLY):\n" + "\n".join(med_lines)

    allergy_lock = ""
    allergies = existing_persona.get('allergies', [])
    if allergies:
        a_lines = []
        for a in allergies:
            if isinstance(a, dict):
                a_lines.append(f"      - {a.get('allergen','')} ({a.get('allergy_type','')}) | {a.get('reaction','')} | {a.get('severity','')}")
        allergy_lock = "\n    - Allergies (LOCK EXACTLY):\n" + "\n".join(a_lines)

    vax_lock = ""
    vaccinations = existing_persona.get('vaccinations', [])
    if vaccinations:
        v_lines = []
        for v in vaccinations:
            if isinstance(v, dict):
                v_lines.append(f"      - {v.get('vaccine_name','')} ({v.get('vaccine_type','')}) | {v.get('date_administered','')} | Reason: {v.get('reason','')}")
        vax_lock = "\n    - Vaccinations (LOCK EXACTLY):\n" + "\n".join(v_lines)

    therapy_lock = ""
    therapies = existing_persona.get('therapies', [])
    if therapies:
        t_lines = []
        for t in therapies:
            if isinstance(t, dict):
                t_lines.append(f"      - [{t.get('status','').upper()}] {t.get('therapy_type','')} | {t.get('provider','')} | {t.get('frequency','')}")
        therapy_lock = "\n    - Therapies (LOCK EXACTLY):\n" + "\n".join(t_lines)

    encounter_lock = ""
    encounters = existing_persona.get('encounters', [])
    if encounters:
        e_lines = []
        for e in encounters:
            if isinstance(e, dict):
                e_lines.append(f"      - {e.get('encounter_date','')} | {e.get('encounter_type','')} | {e.get('chief_complaint','')}")
        encounter_lock = "\n    - Encounters (REPRODUCE EXACTLY, APPEND NEW):\n" + "\n".join(e_lines)

    image_lock = ""
    images = existing_persona.get('images', [])
    if images:
        i_lines = []
        for i in images:
            if isinstance(i, dict):
                i_lines.append(f"      - {i.get('type','')} | {i.get('date','')}")
        image_lock = "\n    - Images (REPRODUCE EXACTLY, APPEND NEW):\n" + "\n".join(i_lines)
        
    report_lock = ""
    reports = existing_persona.get('reports', [])
    if reports:
        r_lines = []
        for r in reports:
            if isinstance(r, dict):
                r_lines.append(f"      - {r.get('type','')} | {r.get('date','')}")
        report_lock = "\n    - Reports (REPRODUCE EXACTLY, APPEND NEW):\n" + "\n".join(r_lines)

    procedure_lock = ""
    procedures = existing_persona.get('procedures', [])
    if procedures:
        p_lines = []
        for p in procedures:
            if isinstance(p, dict):
                p_lines.append(f"      - {p.get('name','')} | {p.get('date','')}")
        procedure_lock = "\n    - Procedures (REPRODUCE EXACTLY, APPEND NEW):\n" + "\n".join(p_lines)

    behavioral_lock = ""
    b_notes = existing_persona.get('behavioral_notes', '')
    if b_notes:
        behavioral_lock = f"\n    - Behavioral Notes (LOCK EXACTLY): {b_notes}"

    return f"""
    **STRICT IDENTITY LOCK (EXISTING PATIENT) — CONSISTENCY ENFORCEMENT:**
    This patient already exists in the database. 
    You MUST reproduce the following core demographic and baseline clinical values verbatim:
    - Name: {existing_persona.get('first_name')} {existing_persona.get('last_name')}
    - DOB: {existing_persona.get('dob')}
    - Gender: {existing_persona.get('gender')}
    - Address: {existing_persona.get('address')}
    - Telecom: {existing_persona.get('telecom')}
    - Provider: {(existing_persona.get('provider') or dict()).get('generalPractitioner')} ({(existing_persona.get('provider') or dict()).get('managingOrganization')}) [NPI: {(existing_persona.get('provider') or dict()).get('formatted_npi')}]{med_lock}{allergy_lock}{vax_lock}{therapy_lock}{encounter_lock}{image_lock}{report_lock}{procedure_lock}{behavioral_lock}
    
    *Exception*: You MUST generate NEW encounters, vital signs, and adjust the bio narrative to logically support any new requested reports or user feedback.
    - Bio Narrative Strategy: Keep the *style* of the existing bio but update the clinical narrative to match the CURRENT procedure ({case_details['procedure']}) and any newly generated reports.
    
    **🚨 CRITICAL FEEDBACK OVERRIDE RULE 🚨**: 
    IF the User Feedback explicitly requests a change to ANY of these locked fields (e.g., changing the gender, removing an allergy, altering a medication, changing demographics), **USER FEEDBACK TAKES ABSOLUTE PRIOROTY OVER THE STRICT IDENTITY LOCK**. You MUST fulfill the feedback request and update the identity constraints accordingly across ALL generated documents and persona fields.
    """

def get_new_patient_constraint(selected_universe: str, excluded_names: list = None) -> str:
    """
    Generates constraint for creating new patient identity.
    
    CUSTOMIZATION OPTIONS:
    - selected_universe: Which fictional universe to use (e.g., "Marvel", "Seinfeld")
    - excluded_names: List of already-used names to avoid duplicates
    
    EFFECT: Creates diverse, unique characters from pop culture.
    """
    exclusion_instruction = ""
    if excluded_names:
        used_list = ", ".join(excluded_names[:50])  # Limit to 50 to avoid token bloat
        exclusion_instruction = f"**USED NAMES (AVOID THESE):** {used_list}."

    return f"""
    **IDENTITY GENERATION (STRICT DIVERSITY RULES):**
    - **Character Source**: Select a UNIQUE fictional character from the universe of **{selected_universe}** (TV/Movie/Book).
    - **VARIETY MANDATE**: {exclusion_instruction} Select a character NOT in the used list.
    - **Gender Balance**: You MUST randomize gender (Aim for 50% Male / 50% Female across runs).
    - **Demographics**: Generate accurate DOB, Address (matching the show's location), and Telecom.
    - **Provider**: REQUIRED. Generate a GP and Managing Org appropriate for the location.
    - **Bio Narrative**: Create a rich, multi-paragraph medical and social history consistent with the character's background but adapted to the patient scenario.
    
    **FEEDBACK OVERRIDE RULE:**
    IF the User Feedback (below) explicitly specifies a character name (e.g. "Use Spider-Man"), you MUST IGNORE the 'Universe' and 'Used Names' constraints and use the requested character.
    """

# ============================================================================
# USER FEEDBACK FORMATTING
# ============================================================================

def get_feedback_instruction(user_feedback: str) -> str:
    """
    Formats user feedback for inclusion in prompts.
    
    PURPOSE: Allows users to override AI behavior with specific instructions.
    EXAMPLE: "Use Tony Stark as the patient" or "Make the diagnosis more severe"
    """
    if not user_feedback:
        return ""
    
    return f"""
    **USER FEEDBACK / QA CORRECTIONS 🚨 (ABSOLUTE TOPMOST PRIORITY) 🚨:**
    The user has provided specific findings, QA reviews, or explicit change requests. 
    YOU MUST IMPLEMENT THESE CHANGES NO MATTER WHAT. THIS DIRECTIVE OVERRIDES ALL OTHER IDENTITY LOCKS, GENERATION RULES, OR CLINICAL CONSTRAINTS.
    > "{user_feedback}"

    **FEEDBACK IMPLEMENTATION MANDATE:**
    - If feedback requests a DEMOGRAPHIC change (e.g. gender, name, age) or baseline clinical change (e.g. remove an allergy, change a medication), you MUST immediately break the "Strict Identity Lock" and apply the requested change across ALL sections (persona, bio narrative, documents, pronouns).
    - If feedback requests **more supporting reports**, **more observations**, or **clinical timeline** — ADD those to `documents` and enrich `encounters`/`bio_narrative`. The `patient_persona` object remains MANDATORY in the output; never omit it when adding documents.
    - If feedback points out **missing documents** (e.g. ECG, Risk Assessment, Stress Test), you MUST invent and generate those specific documents and add them to the `documents` list. DO NOT wait for a template. Invent a logical JSON structure for the newly requested document. The `patient_persona` MUST still be included.
    - If feedback points out a **missing clinical timeline or history**, you MUST extensively populate the `encounters`, `images`, `reports`, and `procedures` lists AND `bio_narrative` to show a clear longitudinal history matching the findings.
    - If feedback points out **missing physical exam/vital signs**, you MUST populate the `vital_signs` block and add examination findings to the encounters.
    - If feedback points out **missing or empty administrative fields** (e.g. patient phone number, provider address, plan type), you MUST explicitly fill them in the persona and documents with realistic data instead of N/A or defaults.
    """

# ============================================================================
# MEDICAL IMAGE GENERATION PROMPT
# ============================================================================
# Controls AI-generated medical imaging (DALL-E 3 / Imagen 3).
#
# QUALITY TIPS FOR EDITING:
# - Be specific about image type (MRI, CT, X-ray, ECG)
# - Emphasize "authentic" and "medical-grade" for realism
# - Restrict unwanted elements (faces, text, watermarks)
# - Request high contrast for clinical clarity

def get_image_generation_prompt(context: str, image_type: str) -> str:
    """
    Generates prompt for medical image synthesis.
    
    Args:
        context: Clinical context (e.g., "knee injury", "chest pain")
        image_type: Type of scan (e.g., "MRI", "X-ray", "CT", "ECG")
    """
    return f"""A high-fidelity {image_type} radiological scan study, photorealistic and medically accurate, visualizing {context}.

IMAGING REQUIREMENTS:
- Style: AUTHENTIC, MEDICAL-GRADE DICOM/RADIOGRAPH format, photorealistic textures
- Quality: 8k resolution, ultra-high definition, clinical diagnostic fidelity
- Color: Grayscale (except for color Doppler if appropriate), authentic medical imaging
- Contrast: HIGH contrast for expert clinical visualization
- Render: Sharp anatomical detail as seen in professional PACS systems

CRITICAL RESTRICTIONS (Prevent Invalid Output):
- NO HUMANS visible (no faces, no full body shots, no skin surfaces)
- NO BODY PARTS visible (except internal anatomical/skeletal structures as appropriate for the scan)
- NO DOCTORS, medical personnel, or healthcare settings
- NO MEDICAL DEVICES/MACHINES surrounding the scan area
- NO TEXT overlays, labels, timestamps, annotations, or watermarks
- NO patient information, hospital names, or identifiers
- NO equipment or machinery visible in the frame (focus exclusively on the anatomy)
- NO graphic or overtly visceral content (maintain professional radiological distance)

OUTPUT: Just the raw, high-fidelity scan image on a deep black background, mimicking a digital radiograph viewer."""

# ============================================================================
# DOCUMENT REPAIR PROMPT
# ============================================================================
# Used when generated documents fail validation.
# 
# PURPOSE: Fixes formatting issues automatically without regenerating entire document.
# COMMON FIXES: Missing metadata blocks, incorrect markers, forbidden formatting

def get_document_repair_prompt(content: str, errors: list) -> str:
    """
    Generates prompt for fixing invalid document content.
    
    Args:
        content: Original document content that failed validation
        errors: List of validation errors to fix
    
    WHEN THIS RUNS: After doc_validator.py detects issues
    
    Returns:
        Repair instruction prompt
    """
    errors_str = "\n".join([f"- {err}" for err in errors])
    
    return f"""Fix the following Clinical Document content to resolve these specific validation errors:

ERRORS TO FIX:
{errors_str}

ORIGINAL CONTENT:
{content}

REPAIR INSTRUCTIONS:
1. Fix ONLY the listed errors
2. Maintain all clinical content
3. Do not add markdown code blocks
4. Return ONLY the corrected content string
5. Preserve the document structure and formatting

RETURN ONLY THE FIXED CONTENT (no explanations, no code blocks)."""

# ============================================================================
# ANNOTATOR SUMMARY PROMPT - Verification Guide Generation
# ============================================================================
# This prompt generates an annotator-focused verification guide that helps
# validate the generated clinical data against expected outcomes.
# 
# WHEN TO USE: After persona (and optionally documents) are generated
# PURPOSE: Create actionable guidance for manual verification and QA

def get_annotator_summary_prompt(
    case_details: dict,
    patient_persona: dict,
    generated_documents: list = None,
    search_results: dict = None
) -> str:
    """
    Generates prompt for creating an annotator verification guide.
    """
    if hasattr(patient_persona, 'model_dump'):
        persona_dict = patient_persona.model_dump()
    else:
        persona_dict = patient_persona
        
    patient_name = f"{persona_dict.get('first_name', 'Unknown')} {persona_dict.get('last_name', 'Unknown')}"
    bio_narrative = persona_dict.get('bio_narrative', '')
    
    doc_list = "\n".join([f"   - {doc.title_hint if hasattr(doc, 'title_hint') else doc.get('title_hint', 'Unknown')}" for doc in (generated_documents or [])])
    
    return f"""
**TASK: Generate an Annotator Verification Guide**

**PATIENT:** {patient_name}
**CLINICAL SCENARIO:** Expected Outcome: {case_details.get('outcome', 'Unknown')}
**PATIENT BIO NARRATIVE:** {bio_narrative}

**GENERATED CLINICAL DOCUMENTS:**
{doc_list if generated_documents else 'Documents Pending'}

**REQUIRED SECTIONS:**
1. **Case Explanation**: Target Procedure, expected outcome, and rationale.
2. **Medical Details**: Key history, diagnoses, and complexity.
3. **Patient Profile Summary**: Prior concerns, necessity justification.
4. **Verification Pointers**: Key items to verify, supporting evidence, red flags.
"""

def get_concise_summary_prompt(
    case_details: dict,
    patient_persona: dict,
    generated_documents: list = None,
    search_results: dict = None
) -> str:
    """
    Generates prompt for creating a structured clinical summary.
    """
    if hasattr(patient_persona, 'model_dump'):
        persona_dict = patient_persona.model_dump()
    else:
        persona_dict = patient_persona

    patient_name = f"{persona_dict.get('first_name', 'Unknown')} {persona_dict.get('last_name', 'Unknown')}"
    bio_narrative = persona_dict.get('bio_narrative', '')
    doc_list = "\n".join([f"   - {doc.title_hint if hasattr(doc, 'title_hint') else doc.get('title_hint', 'Unknown')}" for doc in (generated_documents or [])])

    return f"""
**TASK: Generate a Structured Clinical Summary for Patient: {patient_name}**

**1. Patient's Clinical Narrative:**
{bio_narrative}

**2. Generated Clinical Documents:**
{doc_list if generated_documents else 'Documents Pending'}

**3. Instructions for Summary Generation (Output as a JSON object):**

You are to act as a clinical analyst. Your task is to synthesize the provided information into a structured, clinically-focused summary. The summary should be structured as follows:

- **test_case_and_overview**: A brief paragraph summarizing the test case details and the case overview.
- **details_from_extraction**: A bulleted list of details from extraction like CPT, ICD codes, and insurance.
- **likelihood_without_documents**: The Likelihood/PA probability without considering any supporting documents.
- **likelihood_change_with_documents**: A bulleted list detailing the Likelihood PA score change considering each document; ex. what happens if an individual report is uploaded (if the report creates a positive impact, or if the gap is still not clear from it).
- **medical_necessity**: Analysis of medical necessity indicating `correct_items` and `gaps_and_issues`.
- **policy_compliance**: Analysis of policy compliance indicating `correct_items` and `gaps_and_issues`.
- **documentation_quality**: Analysis of documentation quality indicating `correct_items` and `gaps_and_issues`.
- **clinical_timeline_strength**: Analysis of clinical timeline strength indicating `correct_items` and `gaps_and_issues`.

**IMPORTANT:**
- The summary must be based *only* on the information provided.
- Do not invent new information.
- The tone should be professional and clinical.
"""

# ============================================================================
# REJECTION / DENIAL GAP INJECTION SYSTEM
# ============================================================================
# Architecture:
#   GAP_ARCHETYPE_POOL   → 20 curated gap archetypes across 5 clinical dimensions
#   _select_gap_archetypes() → weighted sampler that guarantees depth + variety
#   get_rejection_gap_instruction() → builds the prompt block for denial cases
#
# Design principles enforced at the prompt level:
#   • Gaps must span ≥2 documents/sections to be detectable
#   • No section is entirely blank/missing — gaps are EMBEDDED in otherwise valid data
#   • At least 1 high-impact gap per case (Treatment Escalation or Policy-Criteria type)
#   • Gap position, type, and combination vary across runs — no predictable signature
#   • Models cannot detect gaps from a single document read-through

GAP_ARCHETYPE_POOL: list[dict] = [
    # ─── Dimension A: Profile ↔ Behavior Contradictions ───────────────────────
    {
        "id": "PB-001",
        "dimension": "Profile-Behavior",
        "criticality": "medium",
        "name": "Tobacco Denial Contradiction",
        "injection_instruction": (
            "In social_history set tobacco_use to 'Never'. "
            "Within one pulmonologist or respiratory encounter note (doctor_note or observations), "
            "include a passing clinical reference such as 'per prior records, patient has a remote "
            "smoking history' or document SpO2 readings consistently at 93–94% without documented cause. "
            "Do NOT explain the discrepancy anywhere. The contradiction must emerge only when comparing "
            "the social history against the encounter notes side by side."
        ),
    },
    {
        "id": "PB-002",
        "dimension": "Profile-Behavior",
        "criticality": "medium",
        "name": "Alcohol Use Underreporting",
        "injection_instruction": (
            "In social_history set alcohol_use to 'Social' and alcohol_frequency to 'Occasional'. "
            "In the lab reports section (reports list or lab document), include a comprehensive metabolic "
            "panel where GGT is elevated (2–3× ULN), AST/ALT ratio > 2:1, and MCV is borderline high "
            "(96–100 fL). Do not flag these values as abnormal in the clinical impression. The pattern "
            "becomes significant only when the social history alcohol claim is cross-referenced with the "
            "lab panel."
        ),
    },
    {
        "id": "PB-003",
        "dimension": "Profile-Behavior",
        "criticality": "medium",
        "name": "BMI-Dosing Discrepancy",
        "injection_instruction": (
            "Set the patient's documented weight to a value that places BMI above 35 kg/m². "
            "In the medication list, include a weight-dependent drug (e.g., anticoagulant, "
            "chemotherapy agent, or antibiotic) prescribed at a standard dose (not adjusted for obesity). "
            "Do not flag this in any clinical note. The mismatch is only detectable by cross-referencing "
            "the patient's biometrics with the prescription details."
        ),
    },
    {
        "id": "PB-004",
        "dimension": "Profile-Behavior",
        "criticality": "low",
        "name": "Exercise Claim vs. Resting Physiology",
        "injection_instruction": (
            "In social_history set exercise_habits to a highly active pattern (e.g., '5 days/week, "
            "moderate to vigorous aerobic exercise'). In vital_signs_current and within at least two "
            "encounter vital_signs blocks, set resting heart_rate consistently between 92–100 bpm. "
            "No explanation for the elevated resting HR should be documented. The physiologic "
            "inconsistency is only apparent when the exercise claim and HR trend are analyzed together."
        ),
    },
    # ─── Dimension B: Temporal Sequence Violations ─────────────────────────────
    {
        "id": "TS-001",
        "dimension": "Temporal-Sequence",
        "criticality": "medium",
        "name": "Lab Result Predates Ordering Encounter",
        "injection_instruction": (
            "Generate a lab report event in the reports list with a date that is 3–7 days BEFORE "
            "the encounter whose doctor_note references ordering that lab ('ordered CBC and comprehensive "
            "panel'). The ordering encounter must be clearly dated AFTER the lab result. "
            "This violation is only visible when the encounter timeline is mapped against the lab dates."
        ),
    },
    {
        "id": "TS-002",
        "dimension": "Temporal-Sequence",
        "criticality": "medium",
        "name": "Imaging Referenced Before It Was Performed",
        "injection_instruction": (
            "In an early encounter (not the most recent), include a clinical note that references "
            "findings from a specific imaging study (e.g., 'per the MRI from last month, there is...') "
            "but date the actual imaging entry in the images list AFTER that encounter date. "
            "The forward-reference is only detectable by comparing the encounter date against the imaging date."
        ),
    },
    {
        "id": "TS-003",
        "dimension": "Temporal-Sequence",
        "criticality": "high",
        "name": "Active Medication Discontinued in Prior Encounter",
        "injection_instruction": (
            "In the medications list, mark one medication as status 'current' with an active start_date. "
            "In an encounter that predates the current run but is documented in encounter history, "
            "include a note in doctor_note or medications_prescribed explicitly stating this drug was "
            "discontinued due to [adverse reaction / inefficacy / patient preference]. "
            "The medication persists as 'current' in the persona. There must be no reconciliation note "
            "or re-initiation note. Detection requires comparing the medication list against encounter notes."
        ),
    },
    {
        "id": "TS-004",
        "dimension": "Temporal-Sequence",
        "criticality": "medium",
        "name": "Mandated Follow-Up Never Occurred",
        "injection_instruction": (
            "In one encounter's follow_up_instructions, explicitly state a time-bound follow-up "
            "(e.g., 'return in 4 weeks for repeat evaluation and decision on proceeding'). "
            "Ensure no subsequent encounter in the encounters list falls within that window or addresses "
            "the follow-up. The next documented encounter (if any) should be unrelated. "
            "The gap only surfaces when follow-up instructions are mapped against the encounter timeline."
        ),
    },
    # ─── Dimension C: Treatment Escalation Gaps ────────────────────────────────
    {
        "id": "TE-001",
        "dimension": "Treatment-Escalation",
        "criticality": "high",
        "name": "Step Therapy Duration Shortfall",
        "injection_instruction": (
            "In the therapies or medications list, document a conservative first-line therapy "
            "(e.g., physical therapy, NSAIDs trial, dietary intervention) with a start and end date "
            "spanning only 10–14 days. Clinical guidelines and PA criteria for this procedure category "
            "typically require 6–12 weeks of documented conservative management. "
            "The PA request form should cite 'failure of conservative management' without specifying "
            "the duration. Reviewers must manually check the therapy dates to identify the shortfall."
        ),
    },
    {
        "id": "TE-002",
        "dimension": "Treatment-Escalation",
        "criticality": "high",
        "name": "Single-Line Step Therapy Claimed as Multiple",
        "injection_instruction": (
            "In the PA request's previous_treatments field, write a phrase implying multiple "
            "conservative therapies were attempted (e.g., 'including pharmacologic and non-pharmacologic "
            "approaches'). In the actual therapies and medication lists, document only one distinct "
            "conservative treatment. The therapies list must contain exactly one entry relevant to the "
            "condition. Detection requires comparing the PA narrative claim against the documented therapy history."
        ),
    },
    {
        "id": "TE-003",
        "dimension": "Treatment-Escalation",
        "criticality": "medium",
        "name": "Therapy Completion Without Outcome Documentation",
        "injection_instruction": (
            "Add a completed therapy entry (status: 'Completed') for a relevant modality "
            "(physical therapy, occupational therapy, or cardiac rehab). "
            "Ensure there is NO corresponding discharge summary, outcome measure score, "
            "functional assessment, or provider note documenting the result of that therapy. "
            "Clinical encounters following the therapy end date should not reference its outcomes. "
            "The missing outcome is only apparent when the therapy record is compared against encounters."
        ),
    },
    {
        "id": "TE-004",
        "dimension": "Treatment-Escalation",
        "criticality": "high",
        "name": "Specialist Referral Deficit",
        "injection_instruction": (
            "The PA request form should reference specialist evaluation as part of the clinical "
            "justification. In the encounters list, include only GP and primary care visits — no "
            "specialist consult note (no cardiology, orthopedics, gastroenterology, etc.). "
            "If the procedure type typically requires a specialist recommendation, the absence creates "
            "a critical gap. This is detectable only by mapping the PA claim against the encounter "
            "provider specialty records."
        ),
    },
    # ─── Dimension D: Cross-Document Contradictions ────────────────────────────
    {
        "id": "CD-001",
        "dimension": "Cross-Document",
        "criticality": "medium",
        "name": "Diagnosis Severity Drift",
        "injection_instruction": (
            "Select the primary ICD-10 code and use a 'mild' or 'moderate' severity variant "
            "(e.g., use the non-severe modifier or a code that maps to minimal impairment). "
            "In the PA request's clinical_justification and expected_outcome fields, use language "
            "describing a severe, functionally limiting condition that significantly impacts daily "
            "activities. Do not reconcile these severity levels anywhere in the documentation. "
            "Detection requires comparing the coded severity against the clinical narrative language."
        ),
    },
    {
        "id": "CD-002",
        "dimension": "Cross-Document",
        "criticality": "medium",
        "name": "Provider Name Fragmentation",
        "injection_instruction": (
            "In the encounters list, reference a key provider with a slightly different name spelling "
            "or credential format in two separate encounters (e.g., 'Dr. Sarah J. Williams, MD' vs "
            "'Dr. S. Williams'). In one of those encounters, assign a NPI that differs by one digit from "
            "the NPI in the persona's provider record. Do not use an obviously fabricated NPI — make it "
            "a plausible 10-digit number that is simply different. This creates identity ambiguity that "
            "only surfaces when provider identifiers are cross-checked."
        ),
    },
    {
        "id": "CD-003",
        "dimension": "Cross-Document",
        "criticality": "low",
        "name": "Imaging Facility State Inconsistency",
        "injection_instruction": (
            "Add one imaging study in the images list performed at a facility located in a different "
            "state than the patient's home address and the procedure facility. Do not include any "
            "transfer-of-care notes, referral letter, or travel documentation explaining why imaging "
            "occurred out of state. The inconsistency is detectable only when the imaging facility "
            "location is compared against patient's documented address and procedure facility state."
        ),
    },
    {
        "id": "CD-004",
        "dimension": "Cross-Document",
        "criticality": "high",
        "name": "Active vs. Discontinued Medication Contradiction",
        "injection_instruction": (
            "Include a specific medication in the medications list with status 'current'. "
            "In a separate clinical document (consult note or PA request's previous_treatments section), "
            "reference this same medication using past tense and imply it was tried and discontinued "
            "(e.g., 'previously tried [drug] without benefit' or 'patient was unable to tolerate [drug]'). "
            "No reconciliation or re-initiation note should exist. The active vs. discontinued discrepancy "
            "only surfaces when the medication list is cross-referenced against clinical notes."
        ),
    },
    # ─── Dimension E: Policy / Criteria Edge Cases ─────────────────────────────
    {
        "id": "PC-001",
        "dimension": "Policy-Criteria",
        "criticality": "high",
        "name": "Authorization Type Mismatch",
        "injection_instruction": (
            "Set the PA request urgency_level to 'Pre-Service Routine' (standard label). "
            "In the clinical_justification field, include language that conveys clinical urgency "
            "(e.g., 'time-sensitive evaluation', 'risk of irreversible deterioration', "
            "'urgent intervention warranted based on progression'). "
            "The contradiction between routine filing and urgent clinical language requires policy "
            "knowledge about authorization type definitions to detect — it is not obvious on a "
            "single-document review."
        ),
    },
    {
        "id": "PC-002",
        "dimension": "Policy-Criteria",
        "criticality": "high",
        "name": "Units-Requested vs. Treatment Plan Mismatch",
        "injection_instruction": (
            "In the PA request, set units_requested to a specific session count (e.g., '24 sessions'). "
            "In the therapy plan documented within clinical notes or the therapies list, reference a "
            "different session frequency and duration that would yield a different total "
            "(e.g., 2x/week for 8 weeks = 16 sessions). The discrepancy between the authorized "
            "unit count and the documented plan requires both the PA form and the therapy notes "
            "to be read and calculated together."
        ),
    },
    {
        "id": "PC-003",
        "dimension": "Policy-Criteria",
        "criticality": "medium",
        "name": "Diagnosis-CPT Medical Necessity Misalignment",
        "injection_instruction": (
            "Use ICD-10 codes where the primary code correctly maps to the general condition "
            "but omit a required specificity modifier or comorbidity code that payers typically "
            "require to establish medical necessity for this CPT. For example, if the CPT requires "
            "documentation of failed pharmacotherapy, do not include the ICD-10 code for drug "
            "resistance or treatment failure — only include the base condition code. "
            "This gap requires knowledge of payer-specific coverage criteria to identify."
        ),
    },
    {
        "id": "PC-004",
        "dimension": "Policy-Criteria",
        "criticality": "medium",
        "name": "Functional Status Documentation Gap",
        "injection_instruction": (
            "For procedures requiring documented functional impairment (e.g., joint replacement, "
            "bariatric surgery, spinal procedures), include clinical notes that describe subjective "
            "symptoms but omit standardized functional assessment scores (e.g., KOOS, WOMAC, ODI, "
            "SF-36, mMRC dyspnea scale). The PA justification should reference 'significant functional "
            "limitation' without citing a validated instrument score. Many payer policies require "
            "objective functional scores — their absence is not obvious without policy knowledge."
        ),
    },
]

def _select_gap_archetypes(n: int = 3) -> list[dict]:
    """
    Select n gap archetypes from GAP_ARCHETYPE_POOL ensuring:
      - At least 1 high-criticality archetype (Treatment-Escalation or Policy-Criteria)
      - At least 2 different dimensions are represented
      - No two archetypes share the same 'id'
      - Total n is randomized between 2 and 4 unless explicitly overridden
    """
    import random as _random

    pool = GAP_ARCHETYPE_POOL
    n = _random.randint(2, 4)

    # Must-have: one high-impact archetype from TE or PC dimensions
    high_impact = [a for a in pool if a["dimension"] in ("Treatment-Escalation", "Policy-Criteria")]
    must_have = _random.choice(high_impact)

    remaining_pool = [a for a in pool if a["id"] != must_have["id"]]
    fill_count = n - 1

    # Try to get at least one from a different dimension than must_have
    diff_dim = [a for a in remaining_pool if a["dimension"] != must_have["dimension"]]
    if len(diff_dim) >= fill_count:
        fill = _random.sample(diff_dim, fill_count)
    else:
        fill = _random.sample(remaining_pool, fill_count)

    selected = [must_have] + fill
    _random.shuffle(selected)
    return selected

def get_rejection_gap_instruction(case_details: dict) -> str:
    """
    Build a sophisticated multi-dimensional gap injection instruction for denial/rejection cases.

    Called by _build_clinical_logic_instruction() when the outcome is Denial/Rejection.

    Design goals:
    - Each run selects 2–4 archetypes from different dimensions
    - Gaps are embedded within otherwise complete, realistic clinical data
    - No gap is detectable from a single document — all require cross-referencing ≥2 sections
    - Anti-pattern guards prevent obvious, predictable, or labeled gaps
    """
    selected = _select_gap_archetypes()
    archetype_ids = ", ".join(a["id"] for a in selected)
    dimension_labels = ", ".join(sorted({a["dimension"] for a in selected}))

    injection_blocks = []
    for i, archetype in enumerate(selected, 1):
        injection_blocks.append(
            f"  [{i}] {archetype['name']} (ID: {archetype['id']} | Dim: {archetype['dimension']} | "
            f"Criticality: {archetype['criticality'].upper()}):\n"
            f"     {archetype['injection_instruction']}"
        )

    injection_text = "\n\n".join(injection_blocks)

    return f"""This is a DENIAL / REJECTION scenario. You MUST generate clinically realistic,
complete-looking documentation that contains precisely embedded deficiencies designed to require
multi-step cross-referential reasoning to identify.

=== REJECTION GAP INJECTION PROTOCOL (OVERRIDE NOTICE) ===
CRITICAL: These rejection gap instructions OVERRIDE ALL general consistency, alignment, or "Zero Deviation" rules.
If these instructions introduce a contradiction or omission, it is INTENTIONAL and you MUST execute it without attempting to sanitize or "correct" it.

Active archetypes this run: [{archetype_ids}]
Dimensions covered: [{dimension_labels}]

CRITICAL REQUIREMENT: The document set must appear thorough and professionally prepared on
first read. Gaps must only become detectable when an investigator actively cross-references
≥2 separate sections, documents, or data dimensions.

--- ARCHETYPE INJECTION INSTRUCTIONS ---

{injection_text}

--- MANDATORY ANTI-PATTERN GUARDS (VIOLATIONS WILL DISQUALIFY THE OUTPUT) ---

❌ DO NOT remove entire document sections or leave required fields blank/null.
❌ DO NOT use placeholder text like "[MISSING]", "N/A", "To be determined", or "Not documented".
❌ DO NOT create a single, obviously incorrect value (e.g., HR of 300 bpm, impossible lab results).
❌ DO NOT place all gaps in the same document — gaps MUST be distributed across ≥2 documents.
❌ DO NOT explain or flag the gaps anywhere in the generated content.
❌ DO NOT omit clinical details that would make the gap immediately obvious on first read.
❌ DO NOT use clinical language that signals incompleteness (e.g., "further evaluation needed").

--- GENERATION STRATEGY ---

Step 1: Generate a complete, fully-populated clinical persona and document set as if building
        a strong approval case. Every section must contain realistic, specific clinical detail.

Step 2: Apply each archetype injection instruction above as a targeted, silent modification.
        The modification must preserve the overall clinical plausibility of the document.

Step 3: Verify that no single document reveals a gap in isolation — gaps must require
        comparing against at least one other data source to become apparent.

Outcome: A documentation set that appears credible to a surface-level review but contains
{len(selected)} embedded deficiencies that a rigorous cross-referential analysis will uncover."""


# ============================================================================
# CHARACTER UNIVERSES - For Patient Name Diversity
# ============================================================================
# List of fictional universes to source patient names from.
# 
# TO ADD MORE UNIVERSES: Simply append to this list (comma-separated).
# EXAMPLES: "The Wire", "Stranger Things", "Avatar: The Last Airbender"

CHARACTER_UNIVERSES = [
    "Seinfeld", "The Office", "Parks and Rec", "Star Wars", "Marvel", 
    "Harry Potter", "Friends", "Lord of the Rings", "Breaking Bad", 
    "Game of Thrones", "Succession", "The Sopranos", "Grey's Anatomy", 
    "House MD", "Scrubs", "2 Broke Girls", "The Big Bang Theory", 
    "Brooklyn 99", "Superstore"
]
