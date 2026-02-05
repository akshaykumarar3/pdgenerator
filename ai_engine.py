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
import httpx # For disabling HTTP/2 to prevent hangs

# Import centralized prompts
import prompts


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

class PatientCommunication(BaseModel):
    """Patient communication preferences."""
    language: str = Field(..., description="Primary language e.g. 'English', 'Spanish'")
    preferred: bool = Field(True, description="Whether this is the preferred communication method")

class PatientProvider(BaseModel):
    """Care provider details - ALL fields required."""
    generalPractitioner: str = Field(..., description="Full name of primary care provider e.g. 'Dr. Jane Smith, MD'")
    formatted_npi: str = Field(..., description="National Provider Identifier (10 digits) e.g. '1234567890'")
    managingOrganization: str = Field(..., description="Name of managing clinic/hospital e.g. 'Mercy General Hospital'")

class PatientLink(BaseModel):
    """Link to other patient records."""
    other_patient: str = Field("N/A", description="ID of linked patient or 'N/A'")
    link_type: str = Field("N/A", description="Type of link: 'replaces', 'replaced-by', 'refer', 'seealso', or 'N/A'")



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
    bio_narrative: Optional[str] = Field(default="", description="Comprehensive biography/history (HPI, Social, Family). Use plain text, avoid markdown.")

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
    content: str = Field(..., description="The full formatted text content of the document.")


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
    documents: List[GeneratedDocument]
    patient_persona: PatientPersona


def generate_clinical_data(case_details: dict, user_feedback: str = "", history_context: str = "", existing_persona: dict = None, excluded_names: List[str] = None, existing_filenames: List[str] = None) -> 'FinalResult':

    """
    Calls AI to generate clinical data (Persona + Documents) based on the case + feedback + history.
    Values referencing 'existing_persona' are STRICT constraints.
    """
    
    # Construct User Feedback Block
    feedback_instruction = prompts.get_feedback_instruction(user_feedback)

    # Identity Constraints
    if existing_persona:
        identity_constraint = prompts.get_existing_patient_constraint(existing_persona, case_details)

    else:
        # DYNAMIC DIVERSITY LOGIC
        # 1. Select Random Universe
        selected_universe = random.choice(CHARACTER_UNIVERSES)
        
        # 2. Generate identity constraint from prompts module
        identity_constraint = prompts.get_new_patient_constraint(selected_universe, excluded_names)

    # Generate main prompt from centralized prompts module
    prompt = prompts.get_clinical_data_prompt(
        case_details=case_details,
        user_feedback=user_feedback,
        history_context=history_context,
        identity_constraint=identity_constraint,
        feedback_instruction=feedback_instruction,
        existing_filenames=existing_filenames or []
    )

    # Use create_with_completion to get usage stats
    try:
        # Convert system prompt to user prompt for Vertex AI compatibility
        system_role = "user" if PROVIDER == "vertexai" else "system"

        # Standardize arguments
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
                 import json
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
        print(f"   ⚠️ AI Generation Failed: {e}")
        # Return dummy to prevent crash if possible, or re-raise
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
            return response.data[0].url

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
            "messages": [
                {"role": system_role, "content": "You are a document repair bot. Output only the fixed text."},
                {"role": "user", "content": prompt}
            ]
        }
        
        if PROVIDER == "openai":
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        elif PROVIDER == "vertexai":
            # Simplified for vertex
            chat = client.get_model(MODEL_NAME).start_chat()
            resp = chat.send_message(prompt)
            return resp.text
            
    except Exception as e:
        print(f"   ⚠️ Repair Failed: {e}")
        return content # Return original if fix fails
