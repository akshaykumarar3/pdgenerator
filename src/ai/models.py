from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any

class PatientContactPeriod(BaseModel):
    """Period during which contact is valid."""
    start: str = Field(..., description="Start date MM-DD-YYYY")
    end: str = Field(..., description="End date MM-DD-YYYY or 'ongoing'")

class PatientContact(BaseModel):
    """Emergency contact or guardian - ALL fields required."""
    relationship: str = Field(..., description="e.g. 'Next of Kin', 'Mother', 'Spouse', 'Emergency Contact'")
    name: str = Field(..., description="Full name of contact")
    telecom: str = Field(..., description="Phone number e.g. '555-123-4567'")
    address: str = Field(..., description="Full address of contact")
    gender: str = Field(..., description="'male', 'female', 'other'")
    organization: str = Field("N/A", description="Organization name if contact is institutional, else 'N/A'")
    period_start: str = Field(..., description="Date contact relationship started (MM-DD-YYYY)")
    period_end: str = Field("ongoing", description="Date contact relationship ended or 'ongoing'")

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
    units_requested: str = Field(default="1", description="Number of units/sessions/procedures requested. E.g. '1', '12 sessions'")

class PatientCommunication(BaseModel):
    """Patient communication preferences."""
    language: str = Field(..., description="Primary language e.g. 'English', 'Spanish'")
    preferred: bool = Field(True, description="Whether this is the preferred communication method")

class PatientProvider(BaseModel):
    """Care provider details - ALL fields required."""
    generalPractitioner: str = Field(..., description="Full name of primary care provider e.g. 'Dr. Jane Smith, MD'")
    formatted_npi: str = Field(..., description="National Provider Identifier: exactly 10 digits. MUST start with 1, 2, 3, or 4 (CMS rule). e.g. '1234567890', '2198765432', '3041234567'")
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
    start_date: str = Field(..., description="Start date MM-DD-YYYY")
    end_date: str = Field("ongoing", description="End date MM-DD-YYYY or 'ongoing'")
    reason: str = Field(..., description="Clinical reason/indication for this medication")


class AllergyEntry(BaseModel):
    """A single allergy or adverse reaction record."""
    allergen: str = Field(..., description="Allergen name e.g. 'Penicillin', 'Peanuts', 'Latex'")
    allergy_type: str = Field(..., description="'Drug', 'Food', 'Environmental', 'Latex', 'Other'")
    reaction: str = Field(..., description="Allergic reaction description e.g. 'Hives', 'Anaphylaxis', 'Rash'")
    severity: str = Field(..., description="'Mild', 'Moderate', 'Severe', 'Life-threatening'")
    onset_date: str = Field(default="Unknown", description="Date allergy was first recorded MM-DD-YYYY or 'Unknown'")


class VaccinationEntry(BaseModel):
    """A single vaccination record."""
    vaccine_name: str = Field(..., description="Vaccine name e.g. 'Influenza', 'COVID-19 BNT162b2', 'Hepatitis B'")
    vaccine_type: str = Field(..., description="Vaccine platform: 'Inactivated', 'mRNA', 'Live-attenuated', 'Toxoid', 'Subunit', 'Viral vector', 'Other'")
    date_administered: str = Field(..., description="Date administered MM-DD-YYYY")
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
    provider_npi: str = Field(default="", description="Provider NPI: 10 digits starting with 1–4 (CMS rule), or empty string if unknown")
    facility: str = Field(..., description="Facility or clinic name")
    start_date: str = Field(..., description="Start date MM-DD-YYYY")
    end_date: str = Field("ongoing", description="End date MM-DD-YYYY or 'ongoing'")
    frequency: str = Field(..., description="Frequency e.g. '2x/week', 'Weekly', 'Daily'")
    status: str = Field(..., description="'Active', 'Completed', 'Discontinued'")
    reason: str = Field(..., description="Clinical reason/referral justification")
    notes: str = Field(default="", description="Additional clinical notes or observations")

class ImagingEntry(BaseModel):
    """A single imaging study record."""
    type: str = Field(..., description="Type of imaging e.g., 'CT Abdomen W/O Contrast', 'MRI Brain'")
    date: str = Field(..., description="Date of study (MM-DD-YYYY)")
    provider: str = Field(default="", description="Ordering provider")
    facility: str = Field(default="", description="Facility where imaging was performed")
    findings: str = Field(..., description="Impression and clinical findings")

class ReportEntry(BaseModel):
    """A single lab or pathology report record."""
    type: str = Field(..., description="Type of report e.g., 'CBC', 'CMP', 'Biopsy'")
    date: str = Field(..., description="Date of report (MM-DD-YYYY)")
    provider: str = Field(default="", description="Ordering provider")
    results: str = Field(..., description="Key results or values")
    notes: str = Field(default="", description="Additional clinical notes")

class ProcedureEntry(BaseModel):
    """A single clinical procedure record."""
    name: str = Field(..., description="Procedure name e.g., 'Appendectomy', 'Colonoscopy'")
    date: str = Field(..., description="Date performed (MM-DD-YYYY)")
    provider: str = Field(default="", description="Performing provider or surgeon")
    facility: str = Field(default="", description="Facility where procedure was performed")
    reason: str = Field(default="", description="Indication or reason for procedure")
    notes: str = Field(default="", description="Complications or additional notes")


class VitalSigns(BaseModel):
    """Patient vital signs at a point in time. Fields may be null if not recorded."""
    recorded_date: str = Field(..., description="Date vitals were recorded MM-DD-YYYY")
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
    last_medical_visit: Optional[str] = Field(None, description="Date of last appointment MM-DD-YYYY, or null")
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
    encounter_date: str = Field(..., description="Date of encounter MM-DD-YYYY — must follow temporal timeline")
    encounter_type: str = Field(..., description="'Office Visit', 'ER Visit', 'Telehealth', 'Follow-up', 'Specialist Consult', 'Pre-op Evaluation'")
    purpose_of_visit: str = Field(..., description="Primary reason patient came in — concise 1-2 sentence statement")
    provider: str = Field(..., description="Full name and credentials of encounter provider")
    provider_npi: str = Field(default="", description="Provider NPI: 10 digits starting with 1–4 (CMS rule), or empty string if unknown")
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
    provider_abbreviation: str = Field(default="", description="Short provider abbreviation e.g. 'UHC', 'BCBS'")
    provider_policy_url: str = Field(default="", description="Provider policy URL")
    plan_name: str = Field(default="Choice Plus", description="Plan name e.g. 'Gold PPO', 'Choice Plus', 'Medicare Advantage'")
    plan_type: str = Field(default="PPO", description="Plan type: 'PPO', 'HMO', 'EPO', 'POS', 'Medicare', 'Medicaid'")
    plan_id: str = Field(default="", description="Plan identifier from configuration e.g. 'UHC_TX_MA'")
    plan_policy_url: str = Field(default="", description="Plan policy URL")
    member_id: str = Field(default="MBR-999999", description="Member ID on insurance card e.g. 'MBR-123456789'")
    policy_number: str = Field(default="POL-99999", description="Policy number e.g. 'POL-2025-001234'")
    effective_date: str = Field(default="2024-01-01", description="Coverage start date MM-DD-YYYY")
    termination_date: str = Field("ongoing", description="Coverage end date or 'ongoing'")
    copay_amount: str = Field(default="$25", description="Copay amount e.g. '$25', '$50'")
    deductible_amount: str = Field(default="$500", description="Annual deductible e.g. '$500', '$1500'")

class PatientPersona(BaseModel):
    """Complete FHIR-compliant patient persona - ALL fields populated."""
    # Core Demographics
    first_name: str = Field(..., description="Patient first name")
    last_name: str = Field(..., description="Patient last name")
    gender: str = Field(..., description="'male', 'female', 'other'")
    dob: str = Field(..., description="Date of birth MM-DD-YYYY")
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
    expected_procedure_date: str = Field(..., description="Expected date for the procedure (MM-DD-YYYY format, MUST be 7-90 days in the FUTURE from today)")
    procedure_requested: str = Field(..., description="Full name of the procedure being requested (e.g., 'Coronary Artery Bypass Graft')")
    procedure_facility: FacilityDetails = Field(..., description="Healthcare facility where procedure will be performed - MUST be in same state as patient address")
    
    # NEW: Prior Authorization Request
    pa_request: PARequestDetails = Field(..., description="Prior Authorization request form details")
    
    # Narrative
    bio_narrative: Optional[str] = Field(default="", description="Comprehensive biography/history (HPI, Social, Family). Use plain text, avoid markdown.")

    has_fit_fobt_result: Optional[bool] = Field(None, description="True if positive FIT/FOBT result exists (typically for GI procedures)")

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

class StructuredClinicalDoc(BaseModel):
    """
    Layer 1: Raw Structured Content (AI Generation).
    The AI fills these fields. Python Helper formats them.
    """
    doc_id: str = Field(..., description="Document ID (e.g. 'DOC-101').")
    doc_type: str = Field(..., description="Type: 'CONSULT', 'IMAGING', 'LAB', 'DISCHARGE', 'ER_VISIT'.")
    title: str = Field(..., description="Descriptive title e.g. 'Cardiology_Consult'.")
    service_date: str = Field(..., description="MM-DD-YYYY")
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


class ClinicalDataPayload(BaseModel):
    """Public model for consumption (Pure Clinical Data)."""
    model_config = ConfigDict(populate_by_name=True)
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
