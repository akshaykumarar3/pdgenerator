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
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List, Dict, Any
from datetime import datetime
import instructor
import httpx # For disabling HTTP/2 to prevent hangs

# Import centralized prompts
import prompts


# ─── Load Environment ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Check cred/ first, then fallback to root
env_path_cred = os.path.join(BASE_DIR, "cred", ".env")
env_path_root = os.path.join(BASE_DIR, ".env")
env_path = env_path_cred if os.path.exists(env_path_cred) else env_path_root
load_dotenv(env_path)

# PROVIDER CONFIG
PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

ALLOWED_PROVIDERS = ["vertexai", "openai"]

# Model Configuration (Prod vs Test)
MODEL_MAP = {
    "vertexai": {"prod": "gemini-2.5-pro", "test": "gemini-2.5-flash"},
    "openai":   {"prod": "gpt-4o",         "test": "gpt-4o-mini"}
}

# ... (lines 28-30 skipped/implied by patch location, actuall I need to do this carefully)


# Select Model
mode_key = "test" if TEST_MODE else "prod"
MODEL_NAME = MODEL_MAP.get(PROVIDER, {}).get(mode_key, "gemini-2.5-pro")

if TEST_MODE:
    print(f"   ⚡ TEST MODE ACTIVE: Using lightweight model ({MODEL_NAME}) & Minimal Data.")

# Diversity Settings (now imported from prompts.py)
CHARACTER_UNIVERSES = prompts.CHARACTER_UNIVERSES

if PROVIDER not in ALLOWED_PROVIDERS:
    raise ValueError(f"❌ Invalid LLM_PROVIDER in .env: '{PROVIDER}'. Must be one of {ALLOWED_PROVIDERS}")

print(f"   🤖 AI Provider: {PROVIDER.upper()}")

# CLIENT INITIALIZATION
client = None

if PROVIDER == "openai":
    if "OPENAI_API_KEY" not in os.environ:
         raise ValueError("Missing OPENAI_API_KEY in .env")
    client = instructor.from_openai(
        OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            http_client=httpx.Client(http2=False) # Fix for hangs
        )
    )


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
        # Force REST transport to avoid gRPC deadlocks on macOS
        vertexai.init(
            project=project_id, 
            location=location, 
            credentials=creds,
            api_transport="rest"
        )
        
        # 2. Init Instructor with Vertex AI Model
        # Using the specific model instance prevents client/version conflicts
        model = vertexai.generative_models.GenerativeModel(MODEL_NAME)
        client = instructor.from_vertexai(
            client=model,
            mode=instructor.Mode.VERTEXAI_TOOLS,
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

# ===== DATA MODELS (Pydantic) =====

class FacilityDetails(BaseModel):
    """Healthcare facility information for procedure location"""
    facility_name: str = Field(..., description="Name of hospital/clinic (e.g., 'St. Mary's Medical Center', 'Memorial Hospital')")
    street_address: str = Field(..., description="Street address (e.g., '123 Main Street')")
    city: str = Field(..., description="City name")
    state: str = Field(..., description="2-letter state code (e.g., 'CA', 'NY', 'TX')")
    zip_code: str = Field(..., description="5-digit ZIP code matching city/state")
    department: str = Field(..., description="Department/unit (e.g., 'Cardiology Department', 'Surgical Center', 'Radiology')")
    
    def full_address(self) -> str:
        """Returns formatted full address"""
        return f"{self.facility_name}\n{self.street_address}\n{self.city}, {self.state} {self.zip_code}"

class PARequestDetails(BaseModel):
    """Prior Authorization Request Form Details"""
    requesting_provider: str = Field(..., description="Name and credentials of requesting physician (e.g., 'Dr. John Smith, MD, FACC')")
    urgency_level: str = Field(..., description="Routine, Urgent, or Emergency")
    clinical_justification: str = Field(..., description="Medical necessity explanation (2-3 sentences explaining why procedure is needed)")
    supporting_diagnoses: List[str] = Field(..., description="ICD-10 codes with descriptions supporting the request (e.g., ['I25.10 - Atherosclerotic heart disease'])")
    previous_treatments: str = Field(default="None", description="Prior treatments attempted, if any")
    expected_outcome: str = Field(..., description="Expected clinical outcome (e.g., 'Improved cardiac function', 'Pain relief')")

class PatientCommunication(BaseModel):
    """Patient communication preferences."""
    language: str = Field(..., description="Primary language e.g. 'English', 'Spanish'")
    preferred: bool = Field(True, description="Whether this is the preferred communication method")

class PatientProvider(BaseModel):
    """Care provider details - ALL fields required."""
    generalPractitioner: str = Field(..., description="Full name of primary care provider e.g. 'Dr. Jane Smith, MD'")
    formatted_npi: str = Field(..., description="National Provider Identifier (10 digits) e.g. '1234567890'")
    managingOrganization: str = Field(..., description="Name of managing clinic/hospital e.g. 'Mercy General Hospital'")
    address: str = Field(default="123 Medical Center Blvd, Suite 100, City, TX 12345", description="Full address of the provider's clinic/office")
    phone: str = Field(default="555-019-8273", description="Provider's office phone number")

class PatientLink(BaseModel):
    """Link to other patient records."""
    other_patient: str = Field("N/A", description="ID of linked patient or 'N/A'")
    link_type: str = Field("N/A", description="Type of link: 'replaces', 'replaced-by', 'refer', 'seealso', or 'N/A'")


class MedicationEntry(BaseModel):
    """A single medication record (current, past, or ongoing)."""
    brand: str = Field(..., description="Brand name of medication e.g. 'Lipitor'")
    generic_name: str = Field(..., description="Generic name + strength e.g. 'Atorvastatin 20mg'")
    dosage: str = Field(..., description="Dosage instructions e.g. '1 tablet daily', 'BID'")
    qty: str = Field(..., description="Quantity dispensed e.g. '30 tablets', '90 day supply'")
    prescribed_by: str = Field(..., description="Prescribing physician e.g. 'Dr. Jane Smith, MD'")
    status: str = Field(..., description="'current', 'past', or 'ongoing'")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field("ongoing", description="End date YYYY-MM-DD or 'ongoing'")
    reason: str = Field(..., description="Clinical reason/indication for this medication")


class AllergyEntry(BaseModel):
    """A single allergy or adverse reaction record."""
    allergen: str = Field(..., description="Allergen name e.g. 'Penicillin', 'Peanuts', 'Latex'")
    allergy_type: str = Field(..., description="'Drug', 'Food', 'Environmental', 'Latex', 'Other'")
    reaction: str = Field(..., description="Allergic reaction description e.g. 'Hives', 'Anaphylaxis', 'Rash'")
    severity: str = Field(..., description="'Mild', 'Moderate', 'Severe', 'Life-threatening'")
    onset_date: str = Field(default="Unknown", description="Date allergy was first recorded YYYY-MM-DD or 'Unknown'")


class VaccinationEntry(BaseModel):
    """A single vaccination record."""
    vaccine_name: str = Field(..., description="Vaccine name e.g. 'Influenza', 'COVID-19 BNT162b2', 'Hepatitis B'")
    vaccine_type: str = Field(..., description="Vaccine platform: 'Inactivated', 'mRNA', 'Live-attenuated', 'Toxoid', 'Subunit', 'Viral vector', 'Other'")
    date_administered: str = Field(..., description="Date administered YYYY-MM-DD")
    administered_by: str = Field(..., description="Administering provider or facility e.g. 'Dr. Smith', 'CVS Pharmacy'")
    dose_number: str = Field(default="1", description="Dose number e.g. '1', '2', 'Booster'")
    reason: str = Field(..., description="Reason for vaccination: 'Routine Immunization', 'Travel', 'Occupational', 'Post-exposure Prophylaxis', 'Catch-up', 'Other'")


class TherapyEntry(BaseModel):
    """A single therapy or behavioral health session record."""
    therapy_type: str = Field(..., description=(
        "Type: 'Physical', 'Occupational', 'Mental Health / Psychotherapy', "
        "'Medication Management (Psychiatry)', 'Cognitive-Behavioral (CBT)', "
        "'Dialectical Behavior (DBT)', 'EMDR', 'Group Therapy', 'Speech', "
        "'Respiratory', 'Cardiac Rehab', 'Pulmonary Rehab', 'Aquatic', 'Other'"
    ))
    cpt_code: str = Field(..., description="Applicable CPT, HCPCS, or CDT code e.g. '97110', '90834', 'H0035'")
    cpt_description: str = Field(..., description="Full description of the CPT/HCPCS/CDT code")
    icd10_codes: List[str] = Field(default_factory=list, description="Supporting ICD-10 diagnosis codes e.g. ['M54.5 - Low back pain', 'F32.1 - Major depressive disorder']")
    provider: str = Field(..., description="Therapist/provider name e.g. 'Dr. Amy Reed, PT'")
    provider_npi: str = Field(default="", description="Provider NPI (10 digits) if known")
    facility: str = Field(..., description="Facility or clinic name")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field("ongoing", description="End date YYYY-MM-DD or 'ongoing'")
    frequency: str = Field(..., description="Frequency e.g. '2x/week', 'Weekly', 'Daily'")
    status: str = Field(..., description="'Active', 'Completed', 'Discontinued'")
    reason: str = Field(..., description="Clinical reason/referral justification")
    notes: str = Field(default="", description="Additional clinical notes or observations")

class ImagingEntry(BaseModel):
    """A single imaging study record."""
    type: str = Field(..., description="Type of imaging e.g., 'CT Abdomen W/O Contrast', 'MRI Brain'")
    date: str = Field(..., description="Date of study (YYYY-MM-DD)")
    provider: str = Field(default="", description="Ordering provider")
    facility: str = Field(default="", description="Facility where imaging was performed")
    findings: str = Field(..., description="Impression and clinical findings")

class ReportEntry(BaseModel):
    """A single lab or pathology report record."""
    type: str = Field(..., description="Type of report e.g., 'CBC', 'CMP', 'Biopsy'")
    date: str = Field(..., description="Date of report (YYYY-MM-DD)")
    provider: str = Field(default="", description="Ordering provider")
    results: str = Field(..., description="Key results or values")
    notes: str = Field(default="", description="Additional clinical notes")

class ProcedureEntry(BaseModel):
    """A single clinical procedure record."""
    name: str = Field(..., description="Procedure name e.g., 'Appendectomy', 'Colonoscopy'")
    date: str = Field(..., description="Date performed (YYYY-MM-DD)")
    provider: str = Field(default="", description="Performing provider or surgeon")
    facility: str = Field(default="", description="Facility where procedure was performed")
    reason: str = Field(default="", description="Indication or reason for procedure")
    notes: str = Field(default="", description="Complications or additional notes")


class VitalSigns(BaseModel):
    """Patient vital signs at a point in time. Fields may be null if not recorded."""
    recorded_date: str = Field(..., description="Date vitals were recorded YYYY-MM-DD")
    blood_pressure: Optional[str] = Field(None, description="e.g. '130/85 mmHg' or null if not recorded")
    heart_rate: Optional[str] = Field(None, description="e.g. '78 bpm' or null")
    blood_sugar_fasting: Optional[str] = Field(None, description="e.g. '95 mg/dL' or null")
    blood_sugar_postprandial: Optional[str] = Field(None, description="2-hour post-meal glucose e.g. '140 mg/dL' or null")
    bmi: Optional[str] = Field(None, description="e.g. '27.4 kg/m²' or null")
    oxygen_saturation: Optional[str] = Field(None, description="e.g. '98%' or null")
    temperature: Optional[str] = Field(None, description="e.g. '98.6°F' or null")
    respiratory_rate: Optional[str] = Field(None, description="e.g. '16 breaths/min' or null")


class SocialHistory(BaseModel):
    """Patient social, lifestyle, and behavioral history. Fields may be null for some patients."""
    tobacco_use: Optional[str] = Field(None, description="'Never', 'Former smoker - quit YYYY', 'Current - N packs/day', or null")
    tobacco_frequency: Optional[str] = Field(None, description="How often e.g. '1 pack/day for 10 years', or null")
    alcohol_use: Optional[str] = Field(None, description="'Non-drinker', 'Social/Occasional', 'Moderate - N drinks/week', 'Heavy', or null")
    alcohol_frequency: Optional[str] = Field(None, description="e.g. '2-3 beers on weekends', or null")
    illicit_drug_use: Optional[str] = Field(None, description="'None', 'Former - substance, quit YYYY', 'Current - substance', or null")
    substance_history: Optional[str] = Field(None, description="Past substance use disorder or treatment history, or null")
    last_medical_visit: Optional[str] = Field(None, description="Date of last appointment YYYY-MM-DD, or null")
    last_visit_reason: Optional[str] = Field(None, description="Reason for last visit, or null")
    missed_appointment: Optional[bool] = Field(None, description="True if patient recently missed an appointment, or null")
    missed_appointment_reason: Optional[str] = Field(None, description="Reason appointment was missed, or null")
    early_visit_reason: Optional[str] = Field(None, description="Reason patient came early/unscheduled, or null")
    mental_health_history: Optional[str] = Field(None, description="Past mental health diagnoses e.g. 'Depression (2020-2022)', or null")
    mental_health_current: Optional[str] = Field(None, description="Current mental health status / PHQ-9 / GAD-7 screening result, or null")
    exercise_habits: Optional[str] = Field(None, description="e.g. 'Walks 3x/week', 'Sedentary', or null")
    diet_notes: Optional[str] = Field(None, description="Dietary patterns e.g. 'Low sodium diet', 'High fat diet', or null")
    family_history_relevant: Optional[str] = Field(None, description="Relevant family medical history, or null")


class EncounterRecord(BaseModel):
    """A single clinical encounter with full documentation."""
    encounter_date: str = Field(..., description="Date of encounter YYYY-MM-DD — must follow temporal timeline")
    encounter_type: str = Field(..., description="'Office Visit', 'ER Visit', 'Telehealth', 'Follow-up', 'Specialist Consult', 'Pre-op Evaluation'")
    purpose_of_visit: str = Field(..., description="Primary reason patient came in — concise 1-2 sentence statement")
    provider: str = Field(..., description="Full name and credentials of encounter provider")
    provider_npi: str = Field(default="", description="Provider NPI if known")
    facility: str = Field(..., description="Facility/clinic name")
    vital_signs: Optional[VitalSigns] = Field(None, description="Vitals recorded at this encounter, or null")
    chief_complaint: str = Field(..., description="Patient's chief complaint in their own words")
    doctor_note: str = Field(..., description="Full SOAP note — includes HPI, Review of Systems, Physical Exam, Assessment, Plan")
    observations: List[str] = Field(default_factory=list, description="Clinical observations made during encounter")
    procedures_performed: List[str] = Field(default_factory=list, description="Procedures with CPT codes e.g. ['93000 - 12-lead ECG', '99213 - E&M Office Visit']")
    diagnoses: List[str] = Field(default_factory=list, description="ICD-10 diagnoses with codes e.g. ['I25.10 - Atherosclerotic heart disease']")
    medications_prescribed: List[str] = Field(default_factory=list, description="Medications ordered at this encounter")
    care_team: List[str] = Field(default_factory=list, description="All providers on care team for this encounter")
    progress_notes: str = Field(..., description="Clinical progress notes — status relative to prior visits, response to treatment, plan adjustments")
    follow_up_instructions: str = Field(default="", description="Follow-up plan given to patient")


class PayerDetails(BaseModel):
    """Insurance/Payer information - ALL fields required."""
    payer_id: str = Field(default="J1113", description="Payer identifier e.g. 'J1113', 'UHC-001'")
    payer_name: str = Field(default="UnitedHealthcare", description="Full payer name e.g. 'UnitedHealthcare', 'Blue Cross Blue Shield', 'Aetna'")
    plan_name: str = Field(default="Choice Plus", description="Plan name e.g. 'Gold PPO', 'Choice Plus', 'Medicare Advantage'")
    plan_type: str = Field(default="PPO", description="Plan type: 'PPO', 'HMO', 'EPO', 'POS', 'Medicare', 'Medicaid'")
    member_id: str = Field(default="MBR-999999", description="Member ID on insurance card e.g. 'MBR-123456789'")
    policy_number: str = Field(default="POL-99999", description="Policy number e.g. 'POL-2025-001234'")
    effective_date: str = Field(default="2024-01-01", description="Coverage start date YYYY-MM-DD")
    termination_date: str = Field("ongoing", description="Coverage end date or 'ongoing'")
    copay_amount: str = Field(default="$25", description="Copay amount e.g. '$25', '$50'")
    deductible_amount: str = Field(default="$500", description="Annual deductible e.g. '$500', '$1500'")

class PatientPersona(BaseModel):
    """Complete FHIR-compliant patient persona - ALL fields populated."""
    # Core Demographics
    first_name: str = Field(..., description="Patient first name")
    last_name: str = Field(..., description="Patient last name")
    gender: str = Field(..., description="'male', 'female', 'other'")
    dob: str = Field(..., description="Date of birth YYYY-MM-DD")
    address: str = Field(..., description="Full home address with city, state, ZIP")
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
    
    # NEW: Procedure Scheduling & Location
    expected_procedure_date: str = Field(..., description="Expected date for the procedure (YYYY-MM-DD format, MUST be 7-90 days in the FUTURE from today)")
    procedure_requested: str = Field(..., description="Full name of the procedure being requested (e.g., 'Coronary Artery Bypass Graft')")
    procedure_facility: FacilityDetails = Field(..., description="Healthcare facility where procedure will be performed - MUST be in same state as patient address")
    
    # NEW: Prior Authorization Request
    pa_request: PARequestDetails = Field(..., description="Prior Authorization request form details")
    
    # Narrative
    bio_narrative: Optional[str] = Field(default="", description="Comprehensive biography/history (HPI, Social, Family). Use plain text, avoid markdown.")

    # ── Clinical Arrays ─────────────────────────────────────────────────────
    medications: List[MedicationEntry] = Field(
        default_factory=list,
        description="All medications (current, past, ongoing) - include brand, generic, dosage, prescribed_by, status, reason"
    )
    allergies: List[AllergyEntry] = Field(
        default_factory=list,
        description="All known allergies and adverse reactions - include allergen type and severity"
    )
    vaccinations: List[VaccinationEntry] = Field(
        default_factory=list,
        description="Complete vaccination history - include vaccine type (mRNA, Inactivated etc.) and clinical reason"
    )
    therapies: List[TherapyEntry] = Field(
        default_factory=list,
        description="Therapy and behavioral health history with CPT/HCPCS codes and ICD-10 diagnoses"
    )
    behavioral_notes: Optional[str] = Field(
        default="",
        description="Observational behavioral notes: medication adherence, lifestyle habits, mental health flags, substance use history"
    )

    # ── Encounters & Clinical History ───────────────────────────────────────
    encounters: List[EncounterRecord] = Field(
        default_factory=list,
        description="2-5 chronological clinical encounters, each with full SOAP note, vitals, care team, and procedures"
    )
    images: List[ImagingEntry] = Field(
        default_factory=list,
        description="Prior imaging studies related to the chief complaint or history"
    )
    reports: List[ReportEntry] = Field(
        default_factory=list,
        description="Prior laboratory and pathology reports"
    )
    procedures: List[ProcedureEntry] = Field(
        default_factory=list,
        description="Prior surgical and clinical procedures performed"
    )
    social_history: Optional[SocialHistory] = Field(
        None,
        description="Patient social and lifestyle history — tobacco, alcohol, drug use, last visit, mental health"
    )
    vital_signs_current: Optional[VitalSigns] = Field(
        None,
        description="Most recent vital signs reading"
    )
    gender_specific_history: Optional[str] = Field(
        None,
        description="Gender-specific clinical history: OB/GYN for female patients (gravida, para, last Pap, mammogram), urologic for male (PSA, prostate)"
    )


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
    doc_id: str = Field(..., description="Document ID e.g. 'DOC-101'")
    title_hint: str = Field(..., description="Short descriptive title e.g. 'Cardiology_Consult', 'MRI_Knee'")
    content: Any = Field(..., description="The clinical document sections as a structured dictionary matching the provided template.")


class ModifiedSQLRaw(BaseModel):
    """Internal model for AI generation (Structured Data)."""
    updated_sql: str = Field(..., description="The fully rewritten, valid SQL code.")
    changes_summary: str = Field(..., description="A short bulleted list of the changes made to the SQL.")
    structured_documents: List[StructuredClinicalDoc] = Field(..., description="List of structured clinical documents.")
    patient_persona: PatientPersona = Field(..., description="The detailed, structured patient identity.")

class ClinicalDataPayload(BaseModel):
    """Public model for consumption (Pure Clinical Data)."""
    # No SQL fields
    changes_summary: str = Field(..., description="A short summary of the clinical scenario generated.")
    documents: List[GeneratedDocument] = Field(..., alias="structured_documents", description="A MANDATORY list of generated clinical documents (consults, lab reports, imaging, etc.) matching the requested templates.")
    patient_persona: PatientPersona

class VerificationPointers(BaseModel):
    """Verification checklist for annotators."""
    expected_outcome: str = Field(..., description="Expected outcome (Approval/Denial)")
    key_verification_items: List[str] = Field(..., description="List of key items to verify")
    supporting_evidence_checklist: List[str] = Field(..., description="Evidence that should be present")
    red_flags: List[str] = Field(default_factory=list, description="Red flags to watch for")
    document_references: List[Dict[str, str]] = Field(default_factory=list, description="Document references with expected content")

class AnnotatorSummary(BaseModel):
    """Annotator verification guide - created after persona and documents are generated."""
    case_explanation: str = Field(..., description="Explanation of procedure, context, and expected outcome")
    medical_details: str = Field(..., description="Persona-specific medical information and case expectations")
    patient_profile_summary: str = Field(..., description="Prior health concerns, procedure justification, CPT rationale")
    verification_pointers: VerificationPointers = Field(..., description="Key elements to verify against expected outcome")


def generate_clinical_data(
    case_details: dict,
    patient_state: dict,
    document_plan: dict,
    user_feedback: str = "",
    history_context: str = "",
    existing_persona: Optional[Dict] = None,
) -> 'ClinicalDataPayload':
    """
    Calls AI to generate clinical data (Persona + Documents) based on the patient state and plan.
    When existing_persona is provided and the AI omits patient_persona, it is used as fallback.
    """
    
    # 1. Load actual JSON templates from disk
    loaded_templates = {}
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    for tmpl_file in document_plan.get("document_templates", []):
        tmpl_path = os.path.join(templates_dir, tmpl_file)
        if os.path.exists(tmpl_path):
            try:
                with open(tmpl_path, "r", encoding='utf-8') as f:
                    loaded_templates[tmpl_file] = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load template {tmpl_file}: {e}")
                
    # 2. Update document_plan with actual templates
    full_document_plan = {
        "case_type": document_plan.get("case_type"),
        "procedure": document_plan.get("procedure"),
        "document_templates": loaded_templates
    }

    # 3. Generate main prompt from centralized prompts module
    prompt = prompts.get_clinical_data_prompt(
        case_details=case_details,
        patient_state=patient_state,
        document_plan=full_document_plan,
        user_feedback=user_feedback,
        history_context=history_context,
        existing_persona=existing_persona
    )

    # Use create_with_completion to get usage stats
    try:
        # Convert system prompt to user prompt for Vertex AI compatibility
        system_role = "user" if PROVIDER == "vertexai" else "system"

        # Standardize arguments
        kwargs = {
            "model": MODEL_NAME,
            "response_model": ClinicalDataPayload,
            "messages": [
                {"role": system_role, "content": prompts.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }
        
        if PROVIDER == "vertexai":
             print(f"   [DEBUG] Calling Vertex AI Direct (Bypassing Instructor) - Model: {MODEL_NAME}")
             print("   [DEBUG] Sending request...")
             
             try:
                 # Flatten messages for simple prompt (or use chat)
                 # Vertex chat needs history... let's just use the final user prompt + system context
                 # Note: client is Instructor, client.client is GenerativeModel
                 model_instance = client.client 
                 
                 from vertexai.generative_models import GenerationConfig
                 
                 # Prepare Prompt
                 msgs = kwargs['messages']
                 # msgs is a list of dicts: [{'role':..., 'content':...}, ...]
                 full_prompt = f"{msgs[0]['content']}\n\nUser Input:\n{msgs[1]['content']}"
                 
                 resp = model_instance.generate_content(
                    full_prompt,
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                        # response_schema=ModifiedSQL.model_json_schema() # Causing hangs
                    )
                 )
                 
                 print("   [DEBUG] Request complete.")
                 print(f"   [DEBUG] Raw Response Length: {len(resp.text)}")
                 
                 # Handle potential List response (e.g. [Object]) vs Object
                 try:
                     raw_text = resp.text.strip()
                     # Basic cleanup if md block
                     if raw_text.startswith("```json"):
                         raw_text = raw_text[7:]
                     if raw_text.endswith("```"):
                         raw_text = raw_text[:-3]
                     
                     data = json.loads(raw_text)
                     if isinstance(data, list) and len(data) > 0:
                         print("   ⚠️  AI returned a LIST. extracted first item.")
                         data = data[0]
                     
                     response_obj = ClinicalDataPayload.model_validate(data)
                 except ValidationError as ve:
                     # Recover when patient_persona is missing but we have existing_persona + documents
                     if "patient_persona" in str(ve) and existing_persona and isinstance(data, dict):
                         docs = data.get("documents", [])
                         changes = data.get("changes_summary", "Generated with recovery (persona was omitted).")
                         try:
                             persona_obj = PatientPersona.model_validate(existing_persona)
                             response_obj = ClinicalDataPayload(
                                 patient_persona=persona_obj,
                                 documents=docs,
                                 changes_summary=changes,
                             )
                             print("   ⚠️  Recovered: used existing persona (AI omitted patient_persona)")
                         except Exception as recover_err:
                             print(f"   ⚠️  Recovery failed: {recover_err}. Re-raising original error.")
                             raise ve
                     else:
                         raise ve
                 except Exception as e:
                     print(f"   ⚠️  Manual JSON Parsing Failed: {e}. Retrying with strict validate...")
                     response_obj = ClinicalDataPayload.model_validate_json(resp.text)
                 
                 # Fake clean usage for now or extract
                 usage_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                 if resp.usage_metadata:
                     usage_stats["prompt_tokens"] = resp.usage_metadata.prompt_token_count
                     usage_stats["completion_tokens"] = resp.usage_metadata.candidates_token_count
                     usage_stats["total_tokens"] = resp.usage_metadata.total_token_count
                     
                 return response_obj, usage_stats
                 
             except Exception as e:
                 print(f"   ❌ Vertex Direct Call Failed: {e}")
                 # Fallback or raise
                 raise e

        # ORIGINAL PATH FOR OPENAI
        print(f"   [DEBUG] Calling AI Provider: {PROVIDER}, Model: {MODEL_NAME}")
        print("   [DEBUG] Sending request...")
        completion_resp = client.chat.completions.create_with_completion(**kwargs)
        print("   [DEBUG] Request complete.")
        
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
        # Recover when patient_persona omitted (e.g. feedback asked for more docs)
        def _try_recover(exc, completion_obj=None):
            if not existing_persona or "patient_persona" not in str(exc):
                return None
            raw_text = ""
            if completion_obj and hasattr(completion_obj, "choices") and completion_obj.choices:
                raw_text = getattr(completion_obj.choices[0].message, "content", None) or ""
            if not raw_text:
                return None
            raw_text = raw_text.strip()
            for prefix in ("```json\n", "```json", "```"):
                if raw_text.startswith(prefix):
                    raw_text = raw_text[len(prefix):].replace("```", "").strip()
                    break
            try:
                data = json.loads(raw_text)
                if isinstance(data, list) and data:
                    data = data[0]
                docs = data.get("documents", [])
                changes = data.get("changes_summary", "Generated with recovery (persona was omitted).")
                persona_obj = PatientPersona.model_validate(existing_persona)
                return ClinicalDataPayload(patient_persona=persona_obj, documents=docs, changes_summary=changes)
            except (json.JSONDecodeError, ValidationError):
                return None

        try:
            from instructor.core import InstructorRetryException
            if isinstance(e, InstructorRetryException):
                recovered = _try_recover(e, getattr(e, "last_completion", None))
                if recovered:
                    print("   ⚠️  Recovered from OpenAI retry failure: used existing persona")
                    return recovered, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        except ImportError:
            pass
        print(f"   ⚠️ AI Generation Failed: {e}")
        raise e




def generate_clinical_image(context: str, image_type: str, output_path: str = None) -> str:
    """Generates a synthetic medical image based on clinical context using AI."""
    # Get prompt from centralized prompts module
    prompt = prompts.get_image_generation_prompt(context, image_type)
    
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
            image_url = response.data[0].url
            
            if output_path:
                import requests
                img_data = requests.get(image_url).content
                with open(output_path, 'wb') as handler:
                    handler.write(img_data)
                return output_path
            return image_url

    except Exception as e:
        print(f"   ⚠️ Image Generation Failed: {e}")
        return None

def fix_document_content(content: str, errors: List[str]) -> str:
    try:
        system_role = "user" if PROVIDER == "vertexai" else "system"
        
        # Get repair prompt from centralized prompts module
        prompt = prompts.get_document_repair_prompt(content, errors)
        
        # Use lightweight model for fixes if possible, or just same model
        # For now reusing the main configured client
        kwargs = {
            "model": MODEL_NAME, # Could use lighter model
            "response_model": str,
            "messages": [
                {"role": system_role, "content": "You are a document repair bot. Output only the fixed text."},
                {"role": "user", "content": prompt}
            ]
        }
        
        if PROVIDER == "openai":
            response = client.chat.completions.create(**kwargs)
            return response
        elif PROVIDER == "vertexai":
            # Simplified for vertex
            chat = client.client.start_chat()
            resp = chat.send_message(prompt)
            return resp.text
            
    except Exception as e:
        print(f"   ⚠️ Repair Failed: {e}")
        return content # Return original if fix fails

def generate_annotator_summary(
    case_details: dict,
    patient_persona,
    generated_documents: list = None,
    search_results: dict = None
) -> AnnotatorSummary:
    """
    Generates an annotator verification guide for QA and validation.
    
    This function creates a comprehensive guide that helps annotators verify
    the generated clinical data against expected outcomes.
    
    FLEXIBLE GENERATION:
    - If generated_documents is provided: Full summary with all 4 sections
    - If generated_documents is None/empty: Partial summary (case explanation + patient profile)
    
    Args:
        case_details: Dict with 'procedure', 'outcome', 'details'
        patient_persona: The generated patient persona (Pydantic object or dict)
        generated_documents: Optional list of generated documents
        search_results: Optional web search results for CPT/ICD codes
    
    Returns:
        AnnotatorSummary object with verification guide content
    """
    
    print(f"   📋 Generating Annotator Verification Guide...")
    
    # Get prompt from centralized prompts module
    prompt = prompts.get_annotator_summary_prompt(
        case_details=case_details,
        patient_persona=patient_persona,
        generated_documents=generated_documents,
        search_results=search_results
    )
    
    try:
        # Convert system prompt to user prompt for Vertex AI compatibility
        system_role = "user" if PROVIDER == "vertexai" else "system"
        
        system_prompt = """You are an expert clinical data analyst creating verification guides for annotators.
Your task is to analyze patient data and create actionable checklists for quality assurance.
Focus on being specific, clear, and helpful for non-clinical annotators."""
        
        kwargs = {
            "model": MODEL_NAME,
            "response_model": AnnotatorSummary,
            "messages": [
                {"role": system_role, "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
        if PROVIDER == "vertexai":
            print(f"   [DEBUG] Calling Vertex AI for Annotator Summary - Model: {MODEL_NAME}")
            
            try:
                model_instance = client.client
                from vertexai.generative_models import GenerationConfig
                
                # Prepare Prompt
                msgs = kwargs['messages']
                full_prompt = f"{msgs[0]['content']}\n\nUser Input:\n{msgs[1]['content']}"
                
                resp = model_instance.generate_content(
                    full_prompt,
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                    )
                )
                
                print(f"   [DEBUG] Annotator Summary Response Length: {len(resp.text)}")
                
                # Parse response
                import json
                try:
                    raw_text = resp.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]
                    
                    data = json.loads(raw_text)
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                    
                    summary_obj = AnnotatorSummary.model_validate(data)
                except Exception as e:
                    print(f"   ⚠️  Manual JSON Parsing Failed: {e}. Retrying with strict validate...")
                    summary_obj = AnnotatorSummary.model_validate_json(resp.text)
                
                print(f"   ✅ Annotator Summary Generated Successfully")
                return summary_obj
                
            except Exception as e:
                print(f"   ❌ Vertex AI Annotator Summary Failed: {e}")
                raise e
        
        # OPENAI PATH
        print(f"   [DEBUG] Calling OpenAI for Annotator Summary - Model: {MODEL_NAME}")
        completion_resp = client.chat.completions.create_with_completion(**kwargs)
        
        # Handle Instructor Tuple Return
        if isinstance(completion_resp, tuple):
            summary_obj = completion_resp[0]
        else:
            summary_obj = completion_resp
        
        if summary_obj is None:
            raise ValueError("AI returned no response for annotator summary")
        
        print(f"   ✅ Annotator Summary Generated Successfully")
        return summary_obj
        
    except Exception as e:
        print(f"   ❌ Annotator Summary Generation Failed: {e}")
        raise e
