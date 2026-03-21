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
7. **Insurance Standardization**: ALL patients must have UnitedHealthcare (UHC) insurance plans with realistic plan details.

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
E. **INSURANCE**: ALWAYS "UnitedHealthcare", Plan: "Medicare Advantage".
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
       - If Target is Denial/Low Probability -> REMOVE supporting evidence or make findings ambiguous/normal.
       - If Target is Approval -> ENSURE strong supporting evidence exists.
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
         - **DOCUMENT OUTPUT FORMAT**:
          For each document template specified in the DOCUMENT PLAN, create a entry in the `documents` list.
          The `content` field MUST contain the fully populated JSON object matching the template structure.
          Do NOT attempt to use markdown or raw text in `content`—it MUST be a structured JSON object.
          The `title_hint` field should match the template's title or logically reflect it.
         - **FEEDBACK-DRIVEN DOCUMENTS (CRITICAL ESCAPE HATCH)**:
           If the USER FEEDBACK mentions missing documents (e.g., "Missing ECG", "No Risk Assessment"), you MUST invent and generate a NEW document for each requested item, even if it is not in the DOCUMENT PLAN. Create a fitting JSON structure for these ad-hoc documents (e.g. `{{"doc_type": "ECG", "findings": "...", "interpretation": "..."}}`) and add them to the `documents` list.
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
       - **Today's Date**: {datetime.datetime.now().strftime("%Y-%m-%d")}
       - **Expected Procedure Date**: MUST be 7-90 days in the FUTURE from today
       - **Timeline Requirements**:
         * Medical history events: 6 months to 5 years BEFORE procedure date
         * Recent encounters/consultations: 1-12 weeks BEFORE procedure date
         * Lab results/diagnostic tests: 1-4 weeks BEFORE procedure date
         * ALL dates in documents must be BEFORE the procedure date
       - **Example Timeline**:
         * Today: 2026-02-17
         * Procedure Date: 2026-03-15 (27 days in future)
         * Recent Consultation: 2026-02-10 (5 days before today)
         * Lab Results: 2026-02-05 (12 days before today)
         * Medical History: 2024-08-15 (18 months ago)
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
    11. **Persona Generation (COMPLETE FHIR-COMPLIANT DATA)**:
       - You MUST populate the `patient_persona` object with ALL fields. **NO NULL VALUES ALLOWED**.
       - **CRITICAL IMPERATIVE**: You MUST rely ONLY on `patient_state` for identifiers, MRN, naming, and demographics. DO NOT CREATE NEW IDENTIFIERS.
       - **Required Fields (ALL MUST BE FILLED)**:
         - `first_name`, `last_name`, `gender`, `dob`, `address`, `telecom`
         - **Biometrics**: `race`, `height`, `weight`
         - `maritalStatus`, `photo` (default placeholder)
         - `communication`, `contact` (Emergency)
         - `provider` (GP), `link` (N/A)
         - **Provider NPI (MANDATORY)**: `provider.formatted_npi`: Format "XXXXXXXXXX" (10 digits)
         - **Clinical Coding (MANDATORY - Must be filled for report alignment)**:
           - `target_cpt_code`: CPT code for the requested procedure
           - `target_cpt_description`: Full procedure description
           - `primary_diagnosis_codes`: List of primary ICD-10 codes
           - `secondary_diagnosis_codes`: List of secondary ICD-10 codes
           - `procedure_history`: List of past relevant procedures
         - **NEW MANDATORY FIELDS (Temporal & Facility)**:
           - `expected_procedure_date`: Future date (YYYY-MM-DD, 7-90 days from today)
           - `procedure_requested`: Full procedure name
           - `procedure_facility`: FacilityDetails object (name, address, city, state, ZIP, department)
           - `pa_request`: PARequestDetails object (all PA form fields)
         - **payer (MANDATORY - UnitedHealthcare ONLY)**:
           - `payer_name`: "UnitedHealthcare"
           - `plan_name`: "Medicare Advantage"
           - `plan_type`: "Medicare Advantage"
           - `policy_number`: Format "POL-YYYY-XXXXXX" (year + 6 digits)
           - All other payer fields (deductible, copay, effective_date)
        - **Bio Narrative (PLAIN TEXT)**:
          - Rich multi-paragraph history (Personality, HPI, Social). NO Markdown.
          - MUST reference the diagnosis codes and clinical history established in the persona.
     12. **MEDICATIONS (MANDATORY — min 3 entries)**:
        - ALL medications MUST be realistic and clinically appropriate for the ICD-10 diagnoses.
        - Mix statuses: some 'current', some 'past', some 'ongoing'.
        - Each MUST have: brand, generic_name (with strength), dosage, qty, prescribed_by (realistic physician), status, start_date, end_date, reason.
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
        - If user provided therapies → use EXACTLY as given. If patient is EXISTING → reproduce from locked constraint.
     16. **BEHAVIORAL NOTES (MANDATORY)**:
        - A concise paragraph: medication adherence, lifestyle habits (diet, exercise, smoking, alcohol), mental health flags, substance use history.
        - Must be consistent with social_history fields.
        - If patient is EXISTING → reproduce behavioral_notes verbatim.
     17. **SOCIAL HISTORY (SocialHistory object — MANDATORY)**:
        - Generate social_history object with all fields. Some may be null at random (realistic variation).
        - tobacco_use, tobacco_frequency, alcohol_use, alcohol_frequency, illicit_drug_use, substance_history
        - last_medical_visit (YYYY-MM-DD), last_visit_reason
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
          * encounter_date (YYYY-MM-DD, must respect temporal timeline)
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
     23. **GENDER-SPECIFIC HISTORY (gender_specific_history)**:
        - Female patients: Include OB/GYN history (gravida/para), last Pap smear date, mammogram date.
        - Male patients: Include PSA level (if age-appropriate), prostate screening history, urologic history.
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
    - Provider: {(existing_persona.get('provider') or dict()).get('generalPractitioner')} ({(existing_persona.get('provider') or dict()).get('managingOrganization')}){med_lock}{allergy_lock}{vax_lock}{therapy_lock}{encounter_lock}{image_lock}{report_lock}{procedure_lock}{behavioral_lock}
    
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
    - If feedback requests **more supporting reports**, **more observations**, or **clinical timeline** — ADD those documents and enrich encounters/bio_narrative. The `patient_persona` object remains MANDATORY in the output; never omit it when adding documents.
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
    
    CUSTOMIZATION GUIDE:
    - Increase quality: Add "ultra-high resolution", "4K medical imaging"
    - Change style: Modify "Black and white" to "color Doppler" for specific scans
    - Add specificity: Include anatomical details like "sagittal view" or "AP projection"
    
    Returns:
        Image generation prompt (max 3900 chars for API limits)
    """
    return f"""A direct, close-up medical {image_type} scan result showing {context}.

IMAGING REQUIREMENTS:
- Style: AUTHENTIC, MEDICAL-GRADE DICOM/RADIOGRAPH format
- Quality: High resolution, clinical diagnostic quality
- Color: Black and white ONLY (grayscale) - authentic medical imaging
- Contrast: HIGH contrast for clear visualization
- View: Professional medical imaging perspective

CRITICAL RESTRICTIONS (Prevent Invalid Output):
- NO HUMANS visible (no faces, no full body shots)
- NO BODY PARTS visible (except internal anatomy/skeletal structures as appropriate)
- NO DOCTORS or medical personnel
- NO MEDICAL DEVICES/MACHINES surrounding the scan
- NO TEXT overlays, labels, annotations, or watermarks
- NO patient information or identifiers
- NO equipment visible in frame

OUTPUT: Just the raw, authentic scan image on a black background, as would appear in a PACS viewer or radiograph film."""

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
    existing_summary: str = None,
    search_results: dict = None
) -> str:
    """
    Generates prompt for creating annotator verification guide.
    
    FLEXIBLE GENERATION:
    - If generated_documents is provided: Full summary with all 4 sections
    - If generated_documents is None/empty: Partial summary (case explanation + patient profile)
    
    This supports the production workflow where:
    1. Persona is generated first
    2. Reports are attached later based on requirements
    3. Summary can be regenerated when reports are added
    
    Args:
        case_details: Dict with 'procedure', 'outcome', 'details'
        patient_persona: The generated patient persona object (dict or Pydantic)
        generated_documents: Optional list of generated documents
        existing_summary: Optional existing summary to update
        search_results: Optional web search results for CPT/ICD codes
    
    Returns:
        Complete prompt string for annotator summary generation
    """
    
    # Extract persona details safely
    if hasattr(patient_persona, 'model_dump'):
        persona_dict = patient_persona.model_dump()
    else:
        persona_dict = patient_persona
    
    patient_name = f"{persona_dict.get('first_name', 'Unknown')} {persona_dict.get('last_name', 'Unknown')}"
    patient_dob = persona_dict.get('dob', '')
    patient_gender = persona_dict.get('gender', '')
    bio_narrative = persona_dict.get('bio_narrative', '')
    
    # Build patient info (only show fields with data)
    patient_info_lines = [f"- Name: {patient_name}"]
    if patient_dob:
        patient_info_lines.append(f"- DOB: {patient_dob}")
    if patient_gender:
        patient_info_lines.append(f"- Gender: {patient_gender}")
    patient_info_section = "\n".join(patient_info_lines)
    
    # Build document list if available
    documents_section = ""
    if generated_documents and len(generated_documents) > 0:
        doc_list = "\n".join([f"   - {doc.title_hint if hasattr(doc, 'title_hint') else doc.get('title_hint', 'Unknown')}" for doc in generated_documents])
        documents_section = f"""
**GENERATED CLINICAL DOCUMENTS ({len(generated_documents)} total):**
{doc_list}

You MUST analyze these documents to create the verification checklist.
"""
    else:
        documents_section = """
**CLINICAL DOCUMENTS STATUS:**
Reports are pending. Clinical documents will be attached later based on requirements.
The verification checklist section should indicate: "Reports pending - verification pointers will be available when clinical documents are generated."
"""
    
    # Determine which sections to generate
    sections_instruction = ""
    if generated_documents and len(generated_documents) > 0:
        sections_instruction = """
**REQUIRED SECTIONS (ALL 4):**

1. **Case Explanation**: 
   - **CRITICAL**: Extract the TARGET CPT CODE and DESCRIPTION from the patient bio narrative above
   - Start with: "Target Procedure: CPT [code] - [description]"
   - Extract ALL CPT codes mentioned in the bio narrative
   - Extract ALL ICD-10 codes with descriptions from the bio narrative
   - Explain the clinical context and patient presentation
   - Explain the expected outcome (Approval/Denial) with clear rationale
   - Include clinical justification for the procedure
   - **NEVER use "N/A"** - if a code is not in the bio narrative, state "See clinical documents for code details"

2. **Medical Details**: 
   - Key medical history elements from the persona
   - How the diagnoses (ICD-10 codes) support or contradict the procedure request
   - Unique or noteworthy aspects of this case
   - Any complicating factors or special considerations
   - Expected documentation elements

3. **Patient Profile Summary**: 
   - Prior health concerns and relevant medical history
   - Medical necessity justification for the target procedure
   - How the CPT code aligns with the patient's condition
   - Procedure justification based on clinical profile
   - Relevant social, lifestyle, or demographic factors

4. **Verification Pointers**: 
   - Key items to verify in the generated documents
   - Supporting evidence that should be present
   - Red flags or inconsistencies to watch for
   - Document-specific expectations (what each document should contain)
"""
    else:
        sections_instruction = """
**REQUIRED SECTIONS (3 of 4 - Documents Pending):**

1. **Case Explanation**: 
   - Start with a clear statement of the TARGET PROCEDURE including CPT code and full description
   - Example: "Target Procedure: CPT 50360 - Renal Transplantation, Kidney Allotransplantation"
   - Explain the clinical context and patient presentation
   - List ALL CPT codes that will be referenced in this case
   - List ALL ICD-10 codes with descriptions (primary and secondary diagnoses)
   - Explain the expected outcome (Approval/Denial) with clear rationale
   - Include clinical justification for the procedure

2. **Medical Details**: 
   - Key medical history elements from the persona
   - How the diagnoses support or contradict the procedure request
   - Unique or noteworthy aspects of this case
   - Expected documentation elements when reports are generated

3. **Patient Profile Summary**: 
   - Prior health concerns and relevant medical history
   - Medical necessity justification for the target procedure
   - How the CPT code aligns with the patient's condition
   - Procedure justification based on clinical profile

4. **Verification Pointers**: 
   INDICATE: "Reports pending - verification checklist will be available when clinical documents are generated."
   INDICATE: "Reports pending - verification checklist will be available when clinical documents are generated."
"""

    # Build reference information section from web search
    reference_section = ""
    if search_results:
        # Add CPT info if available
        if search_results.get('cpt_info'):
            cpt_info = search_results['cpt_info']
            reference_section = f"""

**REFERENCE INFORMATION (Authoritative Source):**

Target CPT Code (from official medical coding database):
- Code: {cpt_info.get('code', 'N/A')}
- Official Description: {cpt_info.get('description', 'N/A')}
- Source: {cpt_info.get('source_url', 'Authoritative medical coding database')}

**IMPORTANT**: Use the official CPT description above when writing the case explanation. This is from an authoritative source and should be referenced accurately.
"""
        
        # Add verification notes if present
        if search_results.get('verification_notes'):
            notes = search_results['verification_notes']
            notes_text = '\n'.join([f"- {note}" for note in notes])
            reference_section += f"""

**DATA QUALITY NOTES (IMPORTANT - Include in Verification Section):**

The following issues were detected during data preparation. These MUST be included in the verification checklist:

{notes_text}

**ACTION REQUIRED**: Add these notes to the "Verification Pointers" section so annotators know what needs manual verification.
"""
    
    return f"""
**TASK: Generate an Annotator Verification Guide**

You are creating a comprehensive guide for clinical data annotators to verify and validate the generated patient data against expected outcomes. This is NOT a clinical document - it is an internal QA tool.

**PATIENT INFORMATION:**
{patient_info_section}

{reference_section}

**CLINICAL SCENARIO (SOURCE OF TRUTH):**
- Expected Outcome: {case_details.get('outcome', 'Unknown')}
- Clinical Context: {case_details.get('details', 'See patient bio narrative')}

**PATIENT BIO NARRATIVE (KEY SOURCE OF MEDICAL INFORMATION):**
{bio_narrative if bio_narrative else 'Not available - extract from generated documents'}

**IMPORTANT**: Extract ALL CPT codes and ICD-10 codes from the bio narrative above. Do NOT show "N/A" - if information is missing, extract it from the bio narrative or indicate it should be verified from the clinical documents.

{documents_section}

{sections_instruction}

**DETAILED INSTRUCTIONS FOR EACH SECTION:**

### 1. Case Explanation
Provide a clear, concise explanation that includes:
- **Extract CPT code and description from the patient bio narrative** (do not use "N/A")
- What procedure is being requested (CPT code and description)
- The clinical context and patient presentation
- The expected outcome (Approval or Denial) and WHY this outcome is expected
- The clinical rationale for this specific case
- List all CPT and ICD-10 codes found in the bio narrative

### 2. Medical Details (Persona-Specific)
Analyze the patient persona and explain:
- Key medical history elements relevant to this case
- How the patient's diagnoses (ICD-10 codes) support or contradict the procedure request
- What makes this case unique or noteworthy
- Any complicating factors or considerations
- What the annotator should expect to see in the clinical documentation

### 3. Patient Profile Summary
Create a comprehensive summary that includes:
- Prior health concerns and medical history
- Why this patient needs this specific procedure (medical necessity)
- How the CPT code aligns with the patient's condition
- Justification for the procedure based on the patient's clinical profile
- Any relevant social or lifestyle factors that impact the case

### 4. Verification Pointers (KEY SECTION FOR ANNOTATORS)
{f'''
Create an actionable checklist based on the expected outcome ({case_details['outcome']}):

**If Expected Outcome is APPROVAL:**
- List specific evidence that MUST be present in the documents to support approval
- Identify which documents should contain supporting findings
- Note any critical test results or clinical findings that justify the procedure
- Highlight alignment between diagnoses and procedure request

**If Expected Outcome is DENIAL:**
- List red flags or missing evidence that should lead to denial
- Identify gaps in clinical justification
- Note any contradictory findings or lack of medical necessity
- Highlight misalignment between diagnoses and procedure request

**General Verification Items:**
- CPT code accuracy and appropriateness
- ICD-10 code validity and medical necessity support
- Consistency across all documents (demographics, dates, findings)
- Completeness of clinical documentation
- Alignment with expected outcome
''' if generated_documents and len(generated_documents) > 0 else 'Indicate that reports are pending and verification checklist will be completed when clinical documents are available.'}

**OUTPUT FORMAT:**
Return a structured JSON object with the following schema:

{{
    "case_explanation": "Detailed explanation of procedure, context, and expected outcome...",
    "medical_details": "Persona-specific medical information and case expectations...",
    "patient_profile_summary": "Prior health concerns, procedure justification, CPT rationale...",
    "verification_pointers": {{
        "expected_outcome": "{case_details['outcome']}",
        "key_verification_items": [
            "Item 1 to verify...",
            "Item 2 to verify...",
            ...
        ],
        "supporting_evidence_checklist": [
            "Evidence 1 that should be present...",
            "Evidence 2 that should be present...",
            ...
        ],
        "red_flags": [
            "Red flag 1 to watch for...",
            "Red flag 2 to watch for...",
            ...
        ],
        "document_references": [
            {{"document": "Document name", "should_contain": "What this document should demonstrate"}},
            ...
        ]
    }}
}}

**CRITICAL RULES:**
1. Write for an ANNOTATOR audience, not a clinical audience
2. Be specific and actionable - avoid vague statements
3. Reference actual CPT and ICD-10 codes from the persona
4. Align verification pointers with the expected outcome
5. Make it easy for annotators to validate the data quality
6. If documents are not available, clearly indicate pending status
"""

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
