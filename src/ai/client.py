import os
import json
from openai import OpenAI
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from vertexai.vision_models import ImageGenerationModel
from google.oauth2 import service_account
from dotenv import load_dotenv
from pydantic import ValidationError
from typing import Optional, List, Dict
import instructor
import httpx # For disabling HTTP/2 to prevent hangs

from . import models
from . import prompts
from . import quality

# ─── Load Environment ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Check cred/ first, then fallback to root
env_path_cred = os.path.join(BASE_DIR, "..", "..", "cred", ".env")
env_path_root = os.path.join(BASE_DIR, "..", "..", ".env")
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

# Select Model
mode_key = "test" if TEST_MODE else "prod"
MODEL_NAME = MODEL_MAP.get(PROVIDER, {}).get(mode_key, "gemini-2.5-pro")

if TEST_MODE:
    print(f"   ⚡ TEST MODE ACTIVE: Using lightweight model ({MODEL_NAME}) & Minimal Data.")

if PROVIDER not in ALLOWED_PROVIDERS:
    raise ValueError(f"❌ Invalid LLM_PROVIDER in .env: ‘{PROVIDER}’. Must be one of {ALLOWED_PROVIDERS}")

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

    # Resolve relative paths against BASE_DIR so the server works regardless of CWD
    if key_path and not os.path.isabs(key_path):
        key_path = os.path.normpath(os.path.join(BASE_DIR, "..", "..", key_path))

    print(f"   🔑 Validating Credentials: {key_path}")
    if not key_path or not os.path.exists(key_path):
        raise ValueError(f"❌ GOOGLE_APPLICATION_CREDENTIALS not found at: {key_path}")

    # Validate JSON integrity & permissions
    try:
        creds = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        print(f"   ✅ Service Account Loaded: {creds.service_account_email}")
    except Exception as e:
        raise ValueError(f"❌ Invalid Service Account Key File: {e}")

    # Auto-correct Zone to Region
    if len(location.split("-")) > 2:
        old_loc = location
        location = "-".join(location.split("-")[:2])
        print(f"   ⚠️ Adjusted GCP_LOCATION from ‘{old_loc}’ to Region ‘{location}’")

    try:
        # Force REST transport to avoid gRPC deadlocks on macOS
        vertexai.init(
            project=project_id,
            location=location,
            credentials=creds,
            api_transport="rest"
        )

        model = GenerativeModel(MODEL_NAME)
        client = instructor.from_vertexai(
            client=model,
            mode=instructor.Mode.VERTEXAI_TOOLS,
        )
    except Exception as e:
        raise RuntimeError(f"❌ Failed to initialize Vertex AI Client: {e}")

# ─── Shared Vertex AI Response Parser ──────────────────────────────────────────

def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from a raw response string."""
    text = text.strip()
    for prefix in ("```json\n", "```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_vertex_response(resp, model_class, existing_persona=None):
    """
    Parse a raw Vertex AI GenerateContent response into a Pydantic model.

    Handles:
    - Markdown JSON fences
    - List unwrapping (AI occasionally returns [{...}])
    - Missing 'patient_persona' recovery when existing_persona is provided
    - Both 'documents' and 'structured_documents' key aliases

    Returns the parsed Pydantic object.
    """
    raw_text = _strip_json_fences(resp.text)
    data = json.loads(raw_text)

    # Unwrap list responses
    if isinstance(data, list) and len(data) > 0:
        print("   ⚠️  AI returned a LIST — extracted first item.")
        data = data[0]

    # Normalise document key: Gemini may return 'documents' instead of 'structured_documents'
    if isinstance(data, dict) and "structured_documents" not in data and "documents" in data:
        data["structured_documents"] = data["documents"]

    try:
        return model_class.model_validate(data)
    except ValidationError as ve:
        # Recovery: if only patient_persona is missing and we have an existing one, inject it
        if "patient_persona" in str(ve) and existing_persona and isinstance(data, dict):
            docs = data.get("structured_documents") or data.get("documents", [])
            changes = data.get("changes_summary", "Generated with recovery (persona was omitted).")
            try:
                persona_obj = models.PatientPersona.model_validate(existing_persona)
                return models.ClinicalDataPayload(
                    patient_persona=persona_obj,
                    documents=docs,
                    changes_summary=changes,
                )
            except Exception as recover_err:
                print(f"   ⚠️  Persona recovery failed: {recover_err}")
        raise ve


def check_connection() -> bool:
    """Pre-flight check to verify LLM reachability."""
    try:
        print(f"   📡 Testing AI Connection... (Model: {MODEL_NAME})", end="", flush=True)
        if PROVIDER == "vertexai":
            model = GenerativeModel(MODEL_NAME)
            resp = model.generate_content("Hello")
            if resp:
                print(" OK! ✅")
                return True
        elif PROVIDER == "openai":
            print(" OK! (OpenAI) ✅")
            return True
        return False
    except Exception as e:
        print(f" FAILED! ❌\n   ⚠️  Connection Error: {e}")
        return False

def generate_clinical_data(
    case_details: dict,
    patient_state: dict,
    document_plan: dict,
    user_feedback: str = "",
    history_context: str = "",
    existing_persona: Optional[Dict] = None,
) -> models.ClinicalDataPayload:
    """
    Calls AI to generate clinical data (Persona + Documents) based on the patient state and plan.
    When existing_persona is provided and the AI omits patient_persona, it is used as fallback.
    """
    
    # 1. Load actual JSON templates from disk
    loaded_templates = {}
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    for tmpl_file in document_plan.get("document_templates", []):
        tmpl_path = os.path.join(templates_dir, tmpl_file)
        if os.path.exists(tmpl_path):
            try:
                with open(tmpl_path, "r", encoding="utf-8") as f:
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

    # Build prompt with an explicit instruction to always include documents
    vertex_doc_reminder = (
        "CRITICAL: Your JSON response MUST contain both 'patient_persona' AND "
        "\'structured_documents\' (an array of at least 1 clinical document). "
        "Never return a response with an empty or missing \'structured_documents\' array."
    )

    try:
        # Convert system prompt to user prompt for Vertex AI compatibility
        system_role = "user" if PROVIDER == "vertexai" else "system"

        # Standardize arguments
        kwargs = {
            "model": MODEL_NAME,
            "response_model": models.ClinicalDataPayload,
            "messages": [
                {"role": system_role, "content": prompts.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }

        if PROVIDER == "vertexai":
            try:
                model_instance = client.client  # GenerativeModel instance
                msgs = kwargs["messages"]
                full_prompt = (
                    f"{vertex_doc_reminder}\n\n"
                    f"{msgs[0]['content']}\n\nUser Input:\n{msgs[1]['content']}"
                )

                # Quantize if input is too large for safe output generation
                full_prompt = quality.quantize_prompt(
                    full_prompt,
                    case_details=case_details,
                    patient_state=patient_state,
                    document_plan={
                        "case_type": document_plan.get("case_type"),
                        "procedure": document_plan.get("procedure"),
                        "document_templates": document_plan.get("document_templates", {}),
                    },
                    user_feedback=user_feedback,
                    history_context=history_context,
                    existing_persona=existing_persona,
                )

                print(f"   🤖 Calling {MODEL_NAME} via Vertex AI ({len(full_prompt):,} chars input)…")
                resp = model_instance.generate_content(
                    full_prompt,
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                        max_output_tokens=65536,
                    )
                )

                tok_in  = getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
                tok_out = getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0
                print(f"   ✅ Response: {len(resp.text):,} chars | tokens in={tok_in} out={tok_out}")

                response_obj = _parse_vertex_response(resp, models.ClinicalDataPayload, existing_persona)
                response_obj = quality.ensure_persona_quality(response_obj, case_details, patient_state)

                usage_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                if resp.usage_metadata:
                    usage_stats["prompt_tokens"] = resp.usage_metadata.prompt_token_count
                    usage_stats["completion_tokens"] = resp.usage_metadata.candidates_token_count
                    usage_stats["total_tokens"] = resp.usage_metadata.total_token_count

                return response_obj, usage_stats

            except Exception as e:
                print(f"   ❌ Vertex Direct Call Failed: {e}")
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
        if completion and hasattr(completion, "usage") and completion.usage:
             usage_stats["prompt_tokens"] = completion.usage.prompt_tokens
             usage_stats["completion_tokens"] = completion.usage.completion_tokens
             usage_stats["total_tokens"] = completion.usage.total_tokens

        response_obj = quality.ensure_persona_quality(response_obj, case_details, patient_state)
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
                persona_obj = models.PatientPersona.model_validate(existing_persona)
                return models.ClinicalDataPayload(patient_persona=persona_obj, documents=docs, changes_summary=changes)
            except (json.JSONDecodeError, ValidationError):
                return None

        try:
            from instructor.core import InstructorRetryException
            if isinstance(e, InstructorRetryException):
                recovered = _try_recover(e, getattr(e, "last_completion", None))
                if recovered:
                    print("   ⚠️  Recovered from OpenAI retry failure: used existing persona")
                    recovered = quality.ensure_persona_quality(recovered, case_details, patient_state)
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
                with open(output_path, "wb") as handler:
                    handler.write(img_data)
                return output_path
            return image_url

    except Exception as e:
        print(f"   ⚠️ Image Generation Failed: {e}")
        return None

def fix_document_content(content: str, errors: List[str]) -> str:
    """
    Attempts to repair a malformed clinical document.

    Args:
        content: The raw document text to repair.
        errors: A list of validation error messages to guide the repair.

    Returns:
        The repaired document string, or the original if repair fails.
    """
    try:
        repair_system = "You are a document repair bot. Output only the fixed text, no explanations."
        prompt = prompts.get_document_repair_prompt(content, errors)
        full_prompt = f"{repair_system}\n\n{prompt}"

        if PROVIDER == "vertexai":
            model_instance = client.client  # GenerativeModel instance
            resp = model_instance.generate_content(full_prompt)
            return resp.text.strip()

        elif PROVIDER == "openai":
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": repair_system},
                    {"role": "user", "content": prompt},
                ]
            )
            if response and response.choices:
                return response.choices[0].message.content or content
            return content

    except Exception as e:
        print(f"   ⚠️ Repair Failed: {e}")
        return content  # Return original if fix fails

def generate_annotator_summary(
    case_details: dict,
    patient_persona,
    generated_documents: list = None,
    search_results: dict = None
) -> models.AnnotatorSummary:
    """
    Generates an annotator verification guide for QA and validation.
    
    This function creates a comprehensive guide that helps annotators verify
    the generated clinical data against expected outcomes.
    
    FLEXIBLE GENERATION:
    - If generated_documents is provided: Full summary with all 4 sections
    - If generated_documents is None/empty: Partial summary (case explanation + patient profile)
    
    Args:
        case_details: Dict with \'procedure\', \'outcome\', \'details\'
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
            "response_model": models.AnnotatorSummary,
            "messages": [
                {"role": system_role, "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
        if PROVIDER == "vertexai":
            print(f"   [DEBUG] Calling Vertex AI for Annotator Summary — Model: {MODEL_NAME}")
            try:
                model_instance = client.client
                msgs = kwargs["messages"]
                full_prompt = f"{msgs[0]['content']}\n\nUser Input:\n{msgs[1]['content']}"

                resp = model_instance.generate_content(
                    full_prompt,
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                    )
                )

                print(f"   [DEBUG] Annotator Summary Response Length: {len(resp.text)}")
                summary_obj = _parse_vertex_response(resp, models.AnnotatorSummary)
                print("   ✅ Annotator Summary Generated Successfully")
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
