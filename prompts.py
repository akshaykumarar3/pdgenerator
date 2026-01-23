"""
AI Prompts Configuration

This file contains all AI prompts and instructions used throughout the application.
Edit these prompts carefully to modify AI behavior.

⚠️ IMPORTANT GUIDELINES FOR EDITING:
1. Maintain the exact structure markers (e.g., "--- REPORT START ---")
2. Keep field names consistent (e.g., PATIENT_ID, MRN, DOB)
3. Test changes thoroughly - incorrect prompts can break document validation
4. Add new instructions at the end of relevant sections
5. Use f-string placeholders (e.g., {case_details['procedure']}) for dynamic values
"""

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

=== CRITICAL PROJECT CONSTRAINTS ===
A. **Data Density**:
   - Documents: Minimum 5 distinct clinical documents.
B. **Clinical Status**:
   - Target Procedure must be 'requested'.
   - Historical Procedures 'completed'.
C. **NO AI RESIDUE**:
   - No "[Redacted]" or "Jane Doe". Use realistic names from Pop Culture Universes (e.g. Characters).
   - Authenticity: 100%.
D. **NAMING CONVENTION**:
   - Use names from: Friends, Marvel, Star Wars, etc. (as per constraints).
E. **INSURANCE REQUIREMENT**:
   - Payer: ALWAYS "UnitedHealthcare" (UHC).
   - Plan Types: Choice Plus PPO, Options PPO, Navigate HMO, or Compass HMO.
   - Include realistic member IDs, group IDs, policy numbers.
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

def get_clinical_data_prompt(case_details: dict, user_feedback: str = "", 
                             history_context: str = "", identity_constraint: str = "",
                             feedback_instruction: str = "", existing_filenames: list = None) -> str:
    """
    Generates the main prompt for clinical data generation.
    
    Args:
        case_details: Dict with 'procedure', 'outcome', 'details'
        user_feedback: Optional user corrections/instructions
        history_context: Previous interaction history
        identity_constraint: Instructions for patient identity (new vs existing)
        feedback_instruction: Formatted feedback block
        existing_filenames: List of existing document titles to avoid duplicates
    
    Returns:
        Complete prompt string
    """
    
    # Build duplicate prevention instruction
    duplicate_prevention = ""
    if existing_filenames:
        duplicate_prevention = f"""
    **DUPLICATE PREVENTION (CRITICAL)**:
    - The following documents ALREADY EXIST for this patient: {', '.join(existing_filenames)}
    - You MUST generate documents with DIFFERENT titles than these existing ones.
    - Focus on new types of clinical evidence not yet documented.
"""
    
    return f"""
    **CLINICAL SCENARIO Requirements (IMMUTABLE Source of Truth):**
    - Procedure: {case_details['procedure']}
    - Target Outcome: {case_details['outcome']}
    - Clinical Context: {case_details['details']}
    
    **PAST HISTORY (CONTEXT):**
    {history_context if history_context else "No prior history available."}

    {feedback_instruction}
{duplicate_prevention}
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
    4. **Medical Coding Requirements (CRITICAL)**:
       - **ICD-10 Codes**: Generate REAL ICD-10-CM diagnosis codes that clinically support the medical necessity of the requested procedure.
       - **CPT Code**: The procedure MUST be specified with its CPT code (e.g., "CPT 78452 - Myocardial perfusion imaging").
       - **Medical Necessity**: ICD-10 codes must be medically appropriate and commonly used to justify the CPT procedure.
       - **Code Format**: ICD-10 codes should follow the format (e.g., "I25.10" for atherosclerotic heart disease, "R07.9" for chest pain).
    5. **Data Density (MANDATORY)**:
       - **Documents**: Minimum 5 distinct clinical documents (e.g., Consult, Lab_Report, Imaging_Report, Discharge_Summary, Specialist_Note).
    6. **Document Generation (CRITICAL Rules)**:
       - Generate `documents` list with rich content.
       - **PROHIBITED TITLES**: No "Approval Letters" or "Denial Notices". Only clinical evidence.
       - **TITLES**: MUST be UNIQUE and DESCRIPTIVE (e.g. "Cardiology_Consult", "Echo_Report").
       - **STRICT FORMATTING (VALIDATOR COMPLIANCE)**:
         - **MUST START WITH**: `--- REPORT START ---`
         - **MUST END WITH**: `--- REPORT END ---`
         - **MUST HAVE METADATA BLOCK**:
           ```text
           [REPORT_METADATA]
           PATIENT_ID: (Use Case ID)
           MRN: (Current MRN)
           PATIENT_NAME: (Full Name)
           DOB: (YYYY-MM-DD)
           REPORT_DATE: (YYYY-MM-DD from Timeline)
           ...
           ```
         - **NO MARKDOWN BOLD**: Do not use `**Text**`.
         - **NO TRIPLE QUOTES**: Do not use `'''`.
       - **METADATA**:
          - `service_date`: Must be logically consistent (Historical dates for evidence, recent for request).
          - `facility_name` & `provider_name`: Realistic and consistent.
    7. **TIMELINE LOGIC (CRITICAL)**:
       - **Target Procedure Date**: Future (e.g. 2-3 weeks from now).
       - **Historical Context**: All Consults, Labs, Imaging must be PAST dated.
       - Example: "Today is 2025-05-01. Requesting procedure for 2025-05-20. Evidence generated from 2025-04-15."
    8. **Persona Generation (COMPLETE FHIR-COMPLIANT DATA)**:
       - You MUST populate the `patient_persona` object with ALL fields. **NO NULL VALUES ALLOWED**.
       {identity_constraint}
       - **Required Fields (ALL MUST BE FILLED)**:
         - `first_name`, `last_name`, `gender`, `dob`, `address`, `telecom`
         - **Biometrics**: `race`, `height`, `weight`
         - `maritalStatus`, `photo` (default placeholder)
         - `communication`, `contact` (Emergency)
         - `provider` (GP), `link` (N/A)
         - **payer (MANDATORY - UnitedHealthcare ONLY)**:
           - `payer_name`: "UnitedHealthcare"
           - `plan_name`: One of "Choice Plus PPO", "Options PPO", "Navigate HMO", "Compass HMO"
           - `plan_type`: "PPO" or "HMO" (must match plan_name)
           - `member_id`: Format "MBR-XXXXXXXXX" (9 digits)
           - `group_id`: Format "GRP-XXXXX" (5 digits)
           - `policy_number`: Format "POL-YYYY-XXXXXX" (year + 6 digits)
           - All other payer fields (deductible, copay, effective_date, subscriber details)
       - **Bio Narrative (PLAIN TEXT)**:
         - Rich multi-paragraph history (Personality, HPI, Social). NO Markdown.
    9. **Output**: Return the `ClinicalDataPayload` JSON.
    """

# ============================================================================
# IDENTITY CONSTRAINTS - Patient Identity Generation Rules
# ============================================================================
# Controls how patient identities are created (new) or maintained (existing).

def get_existing_patient_constraint(existing_persona: dict, case_details: dict) -> str:
    """
    Generates constraint for maintaining existing patient identity.
    
    WHEN TO USE: Patient already exists, updating their records.
    EFFECT: Locks demographics, updates only clinical narrative.
    """
    return f"""
    **STRICT IDENTITY LOCK (EXISTING PATIENT):**
    You MUST use the following demographics. DO NOT CHANGE THEM.
    - Name: {existing_persona.get('first_name')} {existing_persona.get('last_name')}
    - DOB: {existing_persona.get('dob')}
    - Gender: {existing_persona.get('gender')}
    - Address: {existing_persona.get('address')}
    - Telecom: {existing_persona.get('telecom')}
    - Provider: {(existing_persona.get('provider') or {}).get('generalPractitioner')} ({(existing_persona.get('provider') or {}).get('managingOrganization')})
    - Bio Narrative Strategy: Keep the *style* of the existing bio but update the clinical narrative to match the CURRENT procedure ({case_details['procedure']}).
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
    **USER FEEDBACK / QA CORRECTIONS:**
    The user has provided specific instructions for this run. You MUST incorporate them while strictly adhering to the clinical outcome:
    > "{user_feedback}"
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
