import os
import json
import random # For persona diversity
from openai import OpenAI
import vertexai
from vertexai.vision_models import ImageGenerationModel
from google import genai
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import instructor

# Load .env
# Load .env (from cred/ directory)
load_dotenv("cred/.env")

# PROVIDER CONFIG
PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

ALLOWED_PROVIDERS = ["vertexai", "openai"]

# Model Configuration (Prod vs Test)
MODEL_MAP = {
    "vertexai": {"prod": "gemini-2.5-pro", "test": "gemini-2.5-flash"},
    "openai":   {"prod": "gpt-4o",         "test": "gpt-4o-mini"}
}

# Select Model
mode_key = "test" if TEST_MODE else "prod"
MODEL_NAME = MODEL_MAP.get(PROVIDER, {}).get(mode_key, "gemini-2.5-pro")

if TEST_MODE:
    print(f"   ⚡ TEST MODE ACTIVE: Using lightweight model ({MODEL_NAME}) & Minimal Data.")

# Diversity Settings
CHARACTER_UNIVERSES = [
    "Seinfeld", "The Office", "Parks and Rec", "Star Wars", "Marvel", 
    "Harry Potter", "Friends", "Lord of the Rings", "Breaking Bad", 
    "Game of Thrones", "Succession", "The Sopranos", "Grey's Anatomy", 
    "House MD", "Scrubs", "2 Broke Girls", "The Big Bang Theory", 
    "Brooklyn 99", "Superstore"
]

if PROVIDER not in ALLOWED_PROVIDERS:
    raise ValueError(f"❌ Invalid LLM_PROVIDER in .env: '{PROVIDER}'. Must be one of {ALLOWED_PROVIDERS}")

print(f"   🤖 AI Provider: {PROVIDER.upper()}")

# CLIENT INITIALIZATION
client = None

if PROVIDER == "openai":
    if "OPENAI_API_KEY" not in os.environ:
         raise ValueError("Missing OPENAI_API_KEY in .env")
    client = instructor.from_openai(OpenAI())

elif PROVIDER == "vertexai":
    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    location = os.getenv("GCP_LOCATION", "").strip()
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    
    if not project_id or not location:
         raise ValueError("Missing GCP_PROJECT_ID or GCP_LOCATION in .env for Vertex AI")

    print(f"   🔑 Validating Credentials: {key_path}")
    if not key_path or not os.path.exists(key_path):
        raise ValueError(f"❌ GOOGLE_APPLICATION_CREDENTIALS not found at: {key_path}")

    # Validate JSON integrity & Permissions
    try:
        creds = service_account.Credentials.from_service_account_file(
            key_path, 
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        print(f"   ✅ Service Account Loaded: {creds.service_account_email}")
    except Exception as e:
        raise ValueError(f"❌ Invalid Service Account Key File: {e}")

    # Auto-correct Zone to Region
    if len(location.split('-')) > 2:
        old_loc = location
        location = '-'.join(location.split('-')[:2])
        print(f"   ⚠️ Adjusted GCP_LOCATION from '{old_loc}' to Region '{location}'")

    try:
        # 1. Init Vertex SDK
        vertexai.init(project=project_id, location=location, credentials=creds)
        
        # 2. Init Google GenAI Client
        client = instructor.from_genai(
            client=genai.Client(vertexai=True, project=project_id, location=location, credentials=creds),
            mode=instructor.Mode.GENAI_TOOLS,
        )
    except Exception as e:
        raise RuntimeError(f"❌ Failed to initialize Vertex AI Client: {e}")

def check_connection() -> bool:
    """Pre-flight check to verify LLM reachability."""
    try:
        print(f"   📡 Testing AI Connection... (Model: {MODEL_NAME})", end="", flush=True)
        if PROVIDER == "vertexai":
            # Direct SDK call to avoid Instructor retries on Auth fail
            from vertexai.generative_models import GenerativeModel
            model = GenerativeModel(MODEL_NAME)
            resp = model.generate_content("Hello")
            if resp:
                print(" OK! ✅")
                return True

        elif PROVIDER == "openai":
             # Simple client check
             print(" OK! (OpenAI) ✅")
             return True
             
        return False
    except Exception as e:
        print(f" FAILED! ❌\n   ⚠️  Connection Error: {e}")
        return False

class PatientContactPeriod(BaseModel):
    """Period during which contact is valid."""
    start: str = Field(..., description="Start date YYYY-MM-DD")
    end: str = Field(..., description="End date YYYY-MM-DD or 'ongoing'")

class PatientContact(BaseModel):
    """Emergency contact or guardian - ALL fields required."""
    relationship: str = Field(..., description="e.g. 'Next of Kin', 'Mother', 'Spouse', 'Emergency Contact'")
    name: str = Field(..., description="Full name of contact")
    telecom: str = Field(..., description="Phone number e.g. '555-123-4567'")
    address: str = Field(..., description="Full address of contact")
    gender: str = Field(..., description="'male', 'female', 'other'")
    organization: str = Field("N/A", description="Organization name if contact is institutional, else 'N/A'")
    period_start: str = Field(..., description="Date contact relationship started (YYYY-MM-DD)")
    period_end: str = Field("ongoing", description="Date contact relationship ended or 'ongoing'")

class PatientCommunication(BaseModel):
    """Patient communication preferences."""
    language: str = Field(..., description="Primary language e.g. 'English', 'Spanish'")
    preferred: bool = Field(True, description="Whether this is the preferred communication method")

class PatientProvider(BaseModel):
    """Care provider details - ALL fields required."""
    generalPractitioner: str = Field(..., description="Full name of primary care provider e.g. 'Dr. Jane Smith, MD'")
    managingOrganization: str = Field(..., description="Name of managing clinic/hospital e.g. 'Mercy General Hospital'")

class PatientLink(BaseModel):
    """Link to other patient records."""
    other_patient: str = Field("N/A", description="ID of linked patient or 'N/A'")
    link_type: str = Field("N/A", description="Type of link: 'replaces', 'replaced-by', 'refer', 'seealso', or 'N/A'")

class SubscriberDetails(BaseModel):
    """Insurance subscriber details - person who holds the policy."""
    subscriber_id: str = Field(..., description="Subscriber/Member ID e.g. 'MEM-123456789'")
    subscriber_name: str = Field(..., description="Full name of policy holder")
    subscriber_relationship: str = Field(..., description="Relationship to patient: 'Self', 'Spouse', 'Child', 'Other'")
    subscriber_dob: str = Field(..., description="Subscriber date of birth YYYY-MM-DD")
    subscriber_address: str = Field(..., description="Subscriber address if different from patient")

class PayerDetails(BaseModel):
    """Insurance/Payer information - ALL fields required."""
    payer_id: str = Field(..., description="Payer identifier e.g. 'J1113', 'UHC-001'")
    payer_name: str = Field(..., description="Full payer name e.g. 'UnitedHealthcare', 'Blue Cross Blue Shield', 'Aetna'")
    plan_name: str = Field(..., description="Plan name e.g. 'Gold PPO', 'Choice Plus', 'Medicare Advantage'")
    plan_type: str = Field(..., description="Plan type: 'PPO', 'HMO', 'EPO', 'POS', 'Medicare', 'Medicaid'")
    group_id: str = Field(..., description="Group/Employer ID e.g. 'GRP-98765'")
    group_name: str = Field(..., description="Group/Employer name e.g. 'Stark Industries', 'City of Pawnee'")
    member_id: str = Field(..., description="Member ID on insurance card e.g. 'MBR-123456789'")
    policy_number: str = Field(..., description="Policy number e.g. 'POL-2025-001234'")
    effective_date: str = Field(..., description="Coverage start date YYYY-MM-DD")
    termination_date: str = Field("ongoing", description="Coverage end date or 'ongoing'")
    copay_amount: str = Field(..., description="Copay amount e.g. '$25', '$50'")
    deductible_amount: str = Field(..., description="Annual deductible e.g. '$500', '$1500'")
    
    # Subscriber (policy holder)
    subscriber: SubscriberDetails = Field(..., description="Policy holder details")

class PatientPersona(BaseModel):
    """Complete FHIR-compliant patient persona - ALL fields populated."""
    # Core Demographics
    first_name: str = Field(..., description="Patient first name")
    last_name: str = Field(..., description="Patient last name")
    gender: str = Field(..., description="'male', 'female', 'other'")
    dob: str = Field(..., description="Date of birth YYYY-MM-DD")
    address: str = Field(..., description="Full home address")
    telecom: str = Field(..., description="Main phone number e.g. '555-555-5555'")
    
    # Biometrics (New Requirements)
    race: str = Field(..., description="Patient race/ethnicity e.g. 'Caucasian', 'Asian', 'Hispanic'")
    height: str = Field(..., description="Patient height e.g. '5 ft 10 in', '178 cm'")
    weight: str = Field(..., description="Patient weight e.g. '160 lbs', '72 kg'")
    
    # Extended Demographics
    maritalStatus: str = Field(..., description="'Married', 'Single', 'Divorced', 'Widowed', 'Separated'")
    multipleBirthBoolean: bool = Field(False, description="True if part of multiple birth")
    multipleBirthInteger: int = Field(1, description="Birth order if multiple birth, else 1")
    photo: str = Field("placeholder_patient_photo.png", description="Patient photo filename or URL")
    
    # Communication
    communication: PatientCommunication = Field(..., description="Communication preferences")
    
    # Nested Objects - ALL REQUIRED
    contact: PatientContact = Field(..., description="Emergency contact - MUST populate ALL fields: Name, Gender, Address, Telecom, etc.")
    provider: PatientProvider = Field(..., description="Care provider - MUST populate all fields")
    link: PatientLink = Field(default_factory=lambda: PatientLink(), description="Link to other patient records")
    
    # Insurance/Payer - MANDATORY
    payer: PayerDetails = Field(..., description="Insurance/Payer details - MUST populate ALL fields including subscriber")
    
    # Narrative
    bio_narrative: str = Field(..., description="Comprehensive biography/history (HPI, Social, Family). Use plain text, avoid markdown.")

from doc_validator import format_clinical_document

class StructuredClinicalDoc(BaseModel):
    """
    Layer 1: Raw Structured Content (AI Generation).
    The AI fills these fields. Python Helper formats them.
    """
    doc_id: str = Field(..., description="ID matching the SQL insert (e.g. 'DOC-101').")
    doc_type: str = Field(..., description="Type: 'CONSULT', 'IMAGING', 'LAB', 'DISCHARGE', 'ER_VISIT'.")
    title: str = Field(..., description="Descriptive title e.g. 'Cardiology_Consult'.")
    service_date: str = Field(..., description="YYYY-MM-DD")
    facility: str = Field(..., description="Facility Name")
    provider: str = Field(..., description="Provider Name")
    
    # Clinical Sections (Optional - AI fills relevant ones)
    chief_complaint: Optional[str] = None
    hpi: Optional[str] = None
    past_medical_history: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    social_history: Optional[str] = None
    family_history: Optional[str] = None
    review_of_systems: Optional[str] = None
    vitals: Optional[List[str]] = None
    physical_exam: Optional[str] = None
    labs: Optional[List[str]] = None
    imaging: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    
    # Imaging Specific
    exam_type: Optional[str] = None
    indication: Optional[str] = None
    technique: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    
    # Narratives
    narrative: Optional[str] = None # For anything else

class GeneratedDocument(BaseModel):
    """
    Final Output Object (Layer 3).
    Contains the raw content string formatted by Python.
    """
    doc_id: str
    content: str


class ModifiedSQLRaw(BaseModel):
    """Internal model for AI generation (Structured Data)."""
    updated_sql: str = Field(..., description="The fully rewritten, valid SQL code.")
    changes_summary: str = Field(..., description="A short bulleted list of the changes made to the SQL.")
    structured_documents: List[StructuredClinicalDoc] = Field(..., description="List of structured clinical documents.")
    patient_persona: PatientPersona = Field(..., description="The detailed, structured patient identity.")

class ModifiedSQL(BaseModel):
    """Public model for consumption (Formatted Text)."""
    updated_sql: str
    changes_summary: str
    documents: List[GeneratedDocument]
    patient_persona: PatientPersona


def modify_sql(original_sql: str, schema: str, case_details: dict, user_feedback: str = "", history_context: str = "", existing_persona: dict = None, excluded_names: List[str] = None) -> 'FinalResult':

    """
    Calls OpenAI to modify the SQL based on the case + feedback + history.
    Values referencing 'existing_persona' are STRICT constraints.
    """
    
    # Construct User Feedback Block
    feedback_instruction = ""
    if user_feedback:
        feedback_instruction = f"""
        **USER FEEDBACK / QA CORRECTIONS:**
        The user has provided specific instructions for this run. You MUST incorporate them while strictly adhering to the clinical outcome:
        > "{user_feedback}"
        """

    # Identity Constraints
    if existing_persona:
        identity_constraint = f"""
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

    else:
        # DYNAMIC DIVERSITY LOGIC
        # 1. Select Random Universe
        selected_universe = random.choice(CHARACTER_UNIVERSES)
        
        # 2. Build Exclusion String
        exclusion_instruction = ""
        if excluded_names:
            used_list = ", ".join(excluded_names[:50]) # Limit to 50 to avoid token bloat
            exclusion_instruction = f"**USED NAMES (AVOID THESE):** {used_list}."

        identity_constraint = f"""
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

    prompt = f"""
    **DATABASE SCHEMA:**
    {schema}

    **ORIGINAL SQL DATA:**
    {original_sql}
    
    **PAST MODIFICATION HISTORY (CONTEXT):**
    {history_context if history_context else "No prior history available."}

    **NEW SCENARIO REQUIREMENTS (IMMUTABLE Source of Truth):**
    - Procedure: {case_details['procedure']}
    - Target Outcome: {case_details['outcome']}
    - Clinical Context: {case_details['details']}
    
    {feedback_instruction}

    **INSTRUCTIONS:**
    1. Keep the patient ID and demographics unchanged.
    2. **Logic Application**:
       - If Target is Denial/Low Probability -> REMOVE evidence.
       - If Target is Approval -> ENSURE evidence exists.
    3. **Clinical Status**:
       - The *Target Procedure* ({case_details['procedure']}) MUST be in 'status': 'requested'.
       - All *historical* procedures MUST be 'completed'.
    4. **Data Density (MANDATORY)**:
       - You MUST include entries for ALL tables in the schema.
       - **Medications**: Minimum 3 distinct entries.
       - **Observations**: Minimum 3 distinct entries (Vitals, Labs).
       - **Documents**: Minimum 5 distinct clinical documents (e.g., Consult, Lab_Report, Imaging_Report, Discharge_Summary, Specialist_Note).
    5. **Document Generation (CRITICAL Rules)**:
       - generate `documents` list for EVERY `INSERT` into `document_reference_fhir`.
       - **PROHIBITED TITLES**: No "Approval Letters" or "Denial Notices".
       - **TITLES**: MUST be UNIQUE and DESCRIPTIVE (e.g. "Cardiology_Consult", "Echo_Report"). DO NOT use numbers like "Report1".
       - **METADATA consistency**:
          - `service_date`: Must be logically consistent.
          - `facility_name`: Use realistic names (e.g. "Mercy General", "Quest Diagnostics").
          - `provider_name`: Must match the persona's provider network where appropriate.
    6. **TIMELINE LOGIC (CRITICAL)**:
       - **Target Procedure Date**: Set this to a FUTURE date (e.g. 2-3 weeks from now).
       - **Historical Context**: All generated Consults, Labs, and Imaging MUST be dated in the PAST (relative to today) to build the justification for the future procedure.
       - Example: "Today is 2025-05-01. Procedure scheduled for 2025-05-20. MRI was done 2025-04-15."
    7. **MANDATORY**: You MUST include an INSERT statement for `mockdata.patient_info` linking the patient to a payer.
       - Logic: `INSERT INTO mockdata.patient_info (patient_id, payer_id) VALUES ({case_details['id']}, 'J1113');`
       - Default `payer_id` is 'J1113' unless specified otherwise in Feedback.
    8. **ID Handling**: If the input SQL belongs to a different Patient ID, YOU MUST REPLACE IT with the target Patient ID: {case_details['id']}.
    9. **Persona Generation (COMPLETE FHIR-COMPLIANT DATA)**:
       - You MUST populate the `patient_persona` object with ALL fields. **NO NULL VALUES ALLOWED**.
       {identity_constraint}
       - **Required Fields (ALL MUST BE FILLED)**:
         - `first_name`, `last_name`, `gender`, `dob` (YYYY-MM-DD), `address`, `telecom`
         - **Biometrics (TESTING DATA)**: `race`, `height`, `weight` (MUST BE REALISTIC)
         - `maritalStatus`: 'Married', 'Single', 'Divorced', 'Widowed', or 'Separated'
         - `multipleBirthBoolean`: true/false
         - `multipleBirthInteger`: 1 if single birth, else birth order
         - `photo`: 'placeholder_patient_photo.png' (default)
         - `communication`: Object with `language` (e.g. 'English') and `preferred` (true/false)
         - `contact`: Object with ALL fields - `relationship`, `name`, `telecom`, `address`, `gender`, `organization`, `period_start`, `period_end`
         - `provider`: Object with `generalPractitioner` (full name with credentials) and `managingOrganization`
         - `link`: Object with `other_patient` and `link_type` (use 'N/A' if not applicable)
         - `payer` (MANDATORY): Object with ALL insurance fields:
           - `payer_id`, `payer_name`, `plan_name`, `plan_type` (PPO/HMO/EPO/Medicare/Medicaid)
           - `group_id`, `group_name`, `member_id`, `policy_number`
           - `effective_date`, `termination_date`, `copay_amount`, `deductible_amount`
           - `subscriber`: Object with `subscriber_id`, `subscriber_name`, `subscriber_relationship`, `subscriber_dob`, `subscriber_address`
       - **Bio Narrative (PLAIN TEXT)**:
         - Provide a rich, multi-paragraph medical and social history.
         - **CRITICAL**: DO NOT use markdown (**bold**, ## headers). Use plain text only.
         - DO NOT repeat demographics. Focus on: Personality, HPI, Social context, Clinical Logic.
    10. Return the FULL valid SQL using the provided schema.
    
    **G. REFERENCE STANDARD (SAMPLE PERSONA)**:
    - **Header**: Facility Name, Patient Name, DOB, MRN, Date.
    - **Demographics**: Address, Phone, Email, Next of Kin (Name, Relation, Contact), Employer/Occupation.
    - **Insurance**: Payer (UHC), Plan Type, Member ID, Group ID.
    - **Clinical**:
      - **HPI**: Multi-paragraph narrative.
      - **Social**: Living situation, Habits (Smoking/Alcohol with units), Diet, Exercise.
      - **Family**: Detailed 3-generation history.
      - **Current Meds**: Table with Name, Dosage, Freq.
    
    **H. DOCUMENT DENSITY**:
    - Each generated document MUST be **Extensive**.
    - **Consults**: Full SOAP note. Subjective (HPI, ROS), Objective (Vitals, Detailed Exam), Assessment (Diff Dx), Plan.
    - **Imaging**: Technique, Findings (organ by organ), Impression.
    - DO NOT SUMMARIZE. Write as if you are a verbose specialist.
    """

    # Use create_with_completion to get usage stats
    try:
        # Standardize arguments
        kwargs = {
            "response_model": ModifiedSQL,
            "messages": [
                {"role": "system", "content": """
You are **Clinical SQL Generator for Lucenz**, a senior healthcare data architect and FHIR-SQL expert.
Your task: transform one-line clinical use cases into realistic, schema-validated SQL datasets for prior authorization workflows.

=== Core Rules ===
1. Never create or drop tables; only INSERT or UPDATE existing ones defined in the schema.
2. Always insert patient_fhir first, followed by dependent tables in order:
    patient → condition → medication → encounter → observation → procedure → document_reference.
3. Maintain foreign-key integrity and realistic chronological flow.
4. Always align columns exactly with the provided schema.
5. Use realistic medical data (ICD-10, CPT, provider names, facilities, timestamps, labs, vitals).
6. **Inference**: Since you are running in an automated pipeline, if CPT/procedure is not explicitly provided, you MUST INFER the most clinically appropriate code based on the Case Details.
    - Suggestion: Chest pain → 78452 (MPI), 93350 (Stress echo).
    - Suggestion: Knee pain → 73721 (MRI).
7. Suggest CPTs intelligently as per above.
8. **ID Handling**: You WILL receive a Target Patient ID. You must replace ANY existing ID in the template with this Target ID.
9. Output valid, executable SQL.
10. Do not ask clarifying questions; make the best expert decision possible.
11. Always produce valid SQL: explicit column lists, consistent commas/parentheses.
12. Include summary comment headers like -- CONDITIONS, -- MEDICATIONS.
13. **Maintain realistic PA lifecycle**:
    - Initial presentation
    - Diagnostic workup (labs, ECG, stress, imaging)
    - Prior-authorization submission
    - Approval or denial event
    - Discharge/plan note

=== CPT Suggestion Reference ===
• Chest pain → 78452 (MPI), 93350 (Stress echo), 75561 (Cardiac MRI)
• Chronic knee pain → 73721 (Knee MRI), 73562 (X-ray knee 3 views)
• Abdominal pain → 74177 (CT abdomen/pelvis w/ contrast), 76700 (Ultrasound)
• Headache / neuro → 70553 (MRI brain), 70450 (CT head)

=== Output Style ===
• Produce schema-aligned INSERT statements only.
• Use consistent IDs: Patient/###, COND-###, ENC-###, OBS-###, PROC-###, DOC-###.
• Preserve indentation and clear SQL formatting.

=== CRITICAL PROJECT CONSTRAINTS (MUST FOLLOW) ===
A. **Data Density**: You MUST include entries for ALL tables.
   - Medications: Minimum 7 distinct entries.
   - Observations: Minimum 7 distinct entries.
B. **Clinical Status**:
   - Target Procedure ({case_details['procedure']}) Status: 'requested'.
   - Historical Procedures Status: 'completed'.
C. **Payer Linkage**:
   - INSERT INTO mockdata.patient_info (patient_id, payer_id) VALUES ({case_details['id']}, 'J1113');
D. **Document Generation**:
   - For every 'document_reference_fhir' insert, you MUST generate a corresponding 'GeneratedDocument' object in the response list.
   - **PROHIBITED TITLES**: No "Approval Letters" or "Denial Notices". Only clinical evidence (Charts, Labs, Notes).
E. **NO AI RESIDUE (ZERO ACCURACY TOLERANCE)**:
   - **NO REDACTIONS**: Never use "[Redacted]", "John Doe", "Jane Doe", or "Patient X". Use REALISTIC, DIVERSE full names (e.g., "Elena Rodriguez", "Marcus Thorne") and specific dates.
   - **NO META-COMMENTARY**: Do not include headers like "--- Synthetic Data ---" or "Generated by AI".
   - The output must look like a 100% authentic hospital EHR export.
F. **NAMING CONVENTION (HOLLYWOOD/SITCOM)**:
   - You MUST generate patient names based on popular American Sitcoms or Hollywood Fiction (e.g., "Chandler Bing", "Tony Stark", "Leslie Knope", "Walter White", "Ellen Ripley").
   - Do NOT use generic names like "John Smith".
"""},
                {"role": "user", "content": prompt}
            ]
        }
        
        # Add model parameter
        if PROVIDER == "openai":
            kwargs["model"] = "gpt-4o"
        elif PROVIDER == "vertexai":
            # Using Gemini 2.5 Pro as requested
            kwargs["model"] = "gemini-2.5-pro"

        completion_resp = client.chat.completions.create_with_completion(**kwargs)
        
        # Handle Instructor Tuple Return (Response, Completion)
        response_obj = None
        completion = None
        
        if isinstance(completion_resp, tuple):
             response_obj = completion_resp[0]
             completion = completion_resp[1]
        else:
             # Fallback
             response_obj = completion_resp
             
        if response_obj is None:
            print("   ❌ CRITICAL: AI returned NO response object (None).")
            return None

        usage_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if completion and hasattr(completion, 'usage') and completion.usage:
             usage_stats["prompt_tokens"] = completion.usage.prompt_tokens
             usage_stats["completion_tokens"] = completion.usage.completion_tokens
             usage_stats["total_tokens"] = completion.usage.total_tokens

        return response_obj, usage_stats
        
    except Exception as e:
        print(f"   ⚠️ AI Generation Failed: {e}")
        # Return dummy to prevent crash if possible, or re-raise
        raise e




def generate_clinical_image(context: str, image_type: str, output_path: str = None) -> str:
    """
    Generates a synthetic medical image based on the clinical context.
    Uses DALL-E 3 (OpenAI) or Imagen 3 (Gemini/Nano Banana) based on PROVIDER.
    
    Args:
        context: Clinical description.
        image_type: Type of scan (CT, MRI, etc).
        output_path: Optional full path to save the image (Required for Gemini/Imagen).
        
    Returns:
        str: URL if OpenAI (to be downloaded), or local path if Gemini (already saved).
    """
    # Construct a safe, clinical prompt
    prompt = f"""
    A direct, close-up medical {image_type} scan result.
    Clinical Context: {context}.
    Style: AUTHENTIC DICOM/RADIOGRAPH. Black and white ONLY. High contrast.
    CRITICAL RESTRICTIONS:
    - NO HUMANS, NO FACES, NO BODY PARTS visible (except internal anatomy).
    - NO DOCTORS, NO MEDICAL DEVICES/MACHINES surrounding it.
    - NO TEXT, NO LABELS, NO WATERMARKS.
    - Just the raw scan image on a black background (e.g. bones for X-ray, rhythm trace for ECG, brain slice for MRI).
    """
    
    
    try:
        if PROVIDER == "vertexai":
            if not output_path:
                 print("   ⚠️ Vertex Image Gen requires 'output_path'")
                 return None
                 
            # VERTEX AI / IMAGEN (Preview)
            # Ensure Project/Location init is done (it is in global init)
            
            # "imagen-3.0-generate-001" is the common identifier for Imagen 3 on Vertex
            # Updated to 002 based on availability
            model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
            
            response = model.generate_images(
                prompt=prompt[:3900],
                number_of_images=1,
                aspect_ratio="1:1",
            )
            
            # Save to disk
            if response.images:
                response.images[0].save(output_path)
                return output_path
            else:
                return None

        else:
            # OPENAI (DALL-E 3)
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt[:3900], 
                size="1024x1024", 
                quality="standard",
                n=1,
            )
            return response.data[0].url

    except Exception as e:
        print(f"   ⚠️ Image Generation Failed: {e}")
        return None
