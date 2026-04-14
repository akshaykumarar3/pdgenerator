import json
import os
import re
import datetime
import html as html_lib
import traceback
import types

from .data import loader as data_loader
from .ai import client as ai_engine
from .doc_generation import pdf_generator
from .data import history as history_manager
from .core import patient_db
from .data import patient_record_writer
from .core import state as state_manager
from .doc_generation import planner as document_planner
from .doc_generation.validator import validate_structure, format_clinical_document
from .core.config import (
    get_patient_report_folder,
    get_patient_persona_folder,
    get_patient_summary_folder,
)
from .utils.file_utils import get_latest_major_version, get_document_minor_version, archive_patient_files, sanitize_filename_component

def _is_policy_criteria_doc(doc) -> bool:
    """
    Identify payer policy criteria documents to exclude from output for now.
    """
    title = str(getattr(doc, "title_hint", "") or "")
    if re.search(r"(payer\s+policy|policy\s+criteria|policy\s+summary)", title, re.IGNORECASE):
        return True
    try:
        content = doc.content
        if isinstance(content, dict):
            content_text = json.dumps(content)
        else:
            content_text = str(content)
        if re.search(r"(payer\s+policy|policy\s+criteria)", content_text, re.IGNORECASE):
            return True
    except Exception:
        pass
    return False

def _force_positive_outcome(case_details: dict, generation_mode: dict) -> dict:
    """
    For clinical document generation, convert rejection/denial cases to approval
    when supporting reports are being generated.
    """
    if not case_details:
        return case_details
    outcome = str(case_details.get("outcome", "") or "")
    if not generation_mode.get("reports", False):
        return case_details
    if re.search(r"(reject|rejection|deny|denial)", outcome, re.IGNORECASE):
        updated = dict(case_details)
        updated["outcome"] = "PA Approval"
        return updated
    return case_details


def _apply_insurance_overrides(persona, patient_state: dict | None):
    """
    Ensure payer details in persona align with patient_state.insurance.
    """
    if not persona or not patient_state:
        return
    insurance = (patient_state or {}).get("insurance") or {}
    if not insurance:
        return
    payer = getattr(persona, "payer", None)
    if not payer:
        return

    for field in (
        "payer_id",
        "payer_name",
        "plan_name",
        "plan_type",
        "provider_abbreviation",
        "provider_policy_url",
        "plan_id",
        "plan_policy_url",
    ):
        if field in insurance:
            setattr(payer, field, insurance.get(field) or "")

def _augment_feedback_with_risk_assessment(feedback: str, case_details: dict | None = None) -> str:
    """
    If feedback is a JSON risk assessment payload, extract key issues and
    add deterministic remediation instructions for the AI.
    """
    if not feedback or "assessment_found" not in feedback:
        return feedback
    try:
        data = json.loads(feedback)
    except Exception:
        return feedback

    if not isinstance(data, dict):
        return feedback

    category_details = data.get("category_details") or []
    contributing = []
    for c in category_details:
        for item in c.get("contributing_factors") or []:
            contributing.append(str(item))

    contributing_text = "\n".join(f"- {c}" for c in contributing) if contributing else "None detected"

    procedure_text = (case_details or {}).get("procedure", "")
    proc_lower = str(procedure_text).lower()

    # Deterministic remediation rule-set (minimal, calculated)
    rule_lines = []
    if ("colonoscopy" in proc_lower) or ("45378" in proc_lower):
        rule_lines.extend([
            "GI/Colonoscopy Remediation Checklist (ONLY include if clinically consistent):",
            "- Conservative treatments with dates and responses (e.g., dietary modification, hydration plan, antidiarrheal trial, fiber supplementation).",
            "- Diagnostic workup prior to colonoscopy: CBC, CMP, CRP/ESR, stool studies (culture, ova/parasite, C. difficile), fecal calprotectin.",
            "- Specialty evaluation: Gastroenterology consult note referencing persistent symptoms and failed conservative management.",
            "- Risk–benefit analysis: bleeding/perforation risks vs diagnostic yield given symptoms and family history.",
        ])

    remediation = [
        "RISK ASSESSMENT REMEDIATION (STRICT):",
        "You MUST directly address the exact deficiencies listed below with explicit, verifiable clinical evidence.",
        "Do NOT add unrelated or speculative data. Every remediation must be supported by concrete timeline events, tests, and treatments.",
        "Cross-check consistency: any new data must be reflected in persona, encounters, and documents without contradictions.",
        "",
        "Required fixes:",
        "- Document conservative treatment attempts with dates, duration, and response.",
        "- Document a diagnostic workup prior to the requested procedure (labs, imaging, stool studies, specialist evals).",
        "- Include a clear risk-benefit analysis for the requested procedure.",
        "- Include a complete clinical timeline with dated milestones.",
        "- Ensure patient name and DOB are present in primary PA request fields.",
        "- Ensure provider address and plan type are explicitly present.",
        "",
        "Assessment contributing factors:",
        contributing_text,
        "",
        *rule_lines,
        "",
        "When adding any new document to address a missing requirement, create a new document entry in the documents list with a clear title_hint.",
    ]

    remediation_block = "\n".join(remediation)
    if remediation_block in feedback:
        return feedback
    return f"{feedback}\n\n{remediation_block}"

def load_existing_context(patient_id: str, generation_mode: dict) -> dict:
    """
    Load existing documents so the AI can maintain coherence across runs.

    Returns a dict with keys: 'persona', 'reports', 'summary',
    'procedure_date', 'facility'.
    """
    context = {
        "persona": None,
        "reports": [],
        "summary": None,
        "procedure_date": None,
        "facility": None,
    }

    # Load existing persona only when we are NOT regenerating it
    if not generation_mode.get("persona", False):
        existing_patient = patient_db.load_patient(patient_id)
        if existing_patient:
            context["persona"] = existing_patient
            context["procedure_date"] = existing_patient.get("expected_procedure_date")
            facility_data = existing_patient.get("procedure_facility")
            if facility_data:
                context["facility"] = (
                    f"{facility_data.get('facility_name')}, "
                    f"{facility_data.get('city')}, "
                    f"{facility_data.get('state')}"
                )

    # Load existing reports only when we are NOT regenerating them
    if not generation_mode.get("reports", False):
        patient_report_folder = get_patient_report_folder(patient_id)
        if os.path.exists(patient_report_folder):
            report_files = [
                f for f in os.listdir(patient_report_folder)
                if f.endswith(".pdf") and f.startswith(f"DOC-{patient_id}-")
            ]
            context["reports"] = report_files[:5]  # cap for prompt size

    # Load existing summary only when we are NOT regenerating it
    if not generation_mode.get("summary", False):
        summary_folder = get_patient_summary_folder(patient_id)
        if os.path.isdir(summary_folder):
            for f in os.listdir(summary_folder):
                if f.endswith(".pdf") and f.startswith(f"Clinical_Summary_Patient_{patient_id}"):
                    context["summary"] = os.path.join(summary_folder, f)
                    break

    return context

def check_patient_sync_status(patient_id: str, generation_mode: dict) -> bool:
    """
    Return True if ALL documents requested in the generation_mode are already present.
    Returns False if ANY requested document is missing.
    """
    req_persona = generation_mode.get("persona", False)
    req_reports = generation_mode.get("reports", False)
    req_summary = generation_mode.get("summary", False)

    # Note: If a mode is not requested, we treat it as satisfied (True)
    has_persona  = not req_persona
    has_report   = not req_reports
    has_summary  = not req_summary

    # Check Persona
    if req_persona:
        persona_folder = get_patient_persona_folder(patient_id)
        if os.path.isdir(persona_folder):
            has_persona = any(
                f.endswith(".pdf") and "-persona" in f
                for f in os.listdir(persona_folder)
                if f != "archive"
            )

    # Check Reports
    if req_reports:
        rpt_folder = get_patient_report_folder(patient_id)
        if os.path.isdir(rpt_folder):
            has_report = any(
                f.endswith(".pdf") and f.startswith(f"DOC-{patient_id}-")
                for f in os.listdir(rpt_folder)
                if f != "archive"
            )

    # Check Summary
    if req_summary:
        summary_folder = get_patient_summary_folder(patient_id)
        if os.path.isdir(summary_folder):
            has_summary = any(
                f.endswith(".pdf") and f.startswith(f"Clinical_Summary_Patient_{patient_id}")
                for f in os.listdir(summary_folder)
                if f != "archive"
            )

    exists = has_persona and has_report and has_summary
    if not exists:
        missing = []
        if req_persona and not has_persona: missing.append("persona")
        if req_reports and not has_report: missing.append("reports")
        if req_summary and not has_summary: missing.append("summary")
        print(f"   ⚠️  Missing requested documents for patient {patient_id}: {', '.join(missing)}")
        
    return exists

def process_patient_workflow(
    patient_id: str,
    feedback: str = "",
    excluded_names: list[str] = None,
    generation_mode: dict = None,
    cancel_check: callable = None,
    archive_token: str = None,
    generate_rejection_docs: bool = False,
) -> str:
    """
    Main orchestration for a single patient.

    Args:
        patient_id:      Patient ID (string).
        feedback:        Optional free-text AI instructions.
        excluded_names:  List of names already taken (for uniqueness).
        generation_mode: Dict with boolean flags 'persona', 'reports', 'summary'.
                         Defaults to all True.

    Returns:
        The generated full name if successful, else None.
    """
    if excluded_names is None:
        excluded_names = []
    if generation_mode is None:
        generation_mode = {"persona": True, "reports": True, "summary": True}

    # Normalise – ensure all keys present with sane defaults
    generation_mode = {
        "persona": generation_mode.get("persona", False),
        "reports": generation_mode.get("reports", False),
        "summary": generation_mode.get("summary", False),
    }

    print(f"\n🚀 Starting Workflow for Patient ID: {patient_id}")
    print(f"   Mode → Persona:{generation_mode['persona']} | Reports:{generation_mode['reports']} | Summary:{generation_mode['summary']}")

    # ── 1. LOAD CASE DATA ──────────────────────────────────────────────────────
    print(f"\n📂 Loading Case Data for ID: {patient_id}…")
    case_data = data_loader.load_patient_case(patient_id)
    if not case_data:
        print(f"❌ Patient ID '{patient_id}' not found in Excel plan.")
        return None
    print(f"   ✅ Case: {case_data.get('procedure', '?')} → {case_data.get('outcome', '?')}")

    # ── 2. LOAD HISTORY ────────────────────────────────────────────────────────
    history_txt = history_manager.get_history(patient_id)
    if history_txt:
        print("   📜 Prior history loaded.")

    # ── 3. LOAD EXISTING PATIENT RECORD ───────────────────────────────────────
    existing_patient = patient_db.load_patient(patient_id)
    has_persona = bool(existing_patient and (existing_patient.get("first_name") or existing_patient.get("last_name")))
    if has_persona:
        print(f"   🔄 Existing record: {existing_patient.get('first_name')} {existing_patient.get('last_name')}")

    # ── 4. BUILD PATIENT STATE & DOCUMENT PLAN ─────────────────────────────────
    patient_state = state_manager.build_patient_state(patient_id, case_data)
    document_plan = document_planner.create_and_save_document_plan(patient_id, case_data)
    # ── 5. AI GENERATION ───────────────────────────────────────────────────────
    if generate_rejection_docs:
        case_details_for_generation = dict(case_data or {})
    else:
        case_details_for_generation = _force_positive_outcome(case_data or {}, generation_mode)
    
    if case_details_for_generation.get("outcome") != (case_data or {}).get("outcome"):
        print(f"\n🧠 Generating with AI… (Outcome: {case_data.get('outcome', '?')} → {case_details_for_generation.get('outcome', '?')})")
    else:
        print(f"\n🧠 Generating with AI… (Outcome: {case_data.get('outcome', '?')})")
    feedback = _augment_feedback_with_risk_assessment(feedback, case_details=case_data)
    
    if cancel_check and cancel_check():
        print("   ⛔ Cancellation requested before AI generation.")
        return None

    try:
        result, usage = ai_engine.generate_clinical_data(
            case_details=case_details_for_generation,
            patient_state=patient_state,
            document_plan=document_plan,
            user_feedback=feedback,
            history_context=history_txt,
            existing_persona=existing_patient if has_persona else None,
        )
        
        from .doc_generation.validator import validate_npi_consistency
        npi_valid, npi_errors = validate_npi_consistency(result)
        if not npi_valid:
            raise ValueError(f"NPI Consistency Error: {'; '.join(npi_errors)}")
            
    except Exception as e:
        print(f"❌ AI generation failed: {e}")
        return None

    # Persist history entry regardless of subsequent steps
    history_manager.append_history(patient_id, feedback, result.changes_summary)

    # Filter out policy criteria summary documents for now
    documents_all = result.documents or []
    filtered_documents = [doc for doc in documents_all if not _is_policy_criteria_doc(doc)]
    if len(filtered_documents) != len(documents_all):
        removed = len(documents_all) - len(filtered_documents)
        print(f"   🧹 Removed {removed} payer policy criteria document(s) from output.")

    # Ensure payer fields reflect patient_state insurance config/selection
    _apply_insurance_overrides(result.patient_persona, patient_state)

    # ── 6. SAVE PATIENT PERSONA TO DB ─────────────────────────────────────────
    p_full_name = None
    if result.patient_persona:
        db_entry = result.patient_persona.model_dump()
        patient_db.save_patient(patient_id, db_entry)
        p_full_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
        print(f"   💾 Patient DB updated: {p_full_name} (ID {patient_id})")

    # Ensure patient output folder uses "ID - Name" convention when possible
    patient_report_folder = None
    if p_full_name:
        try:
            from .core.config import find_patient_folder, get_patient_root, OUTPUT_DIR
            existing_root = find_patient_folder(patient_id)
            desired_root = get_patient_root(patient_id, p_full_name, prefer_name=True)
            if existing_root and existing_root != desired_root and not os.path.exists(desired_root):
                os.rename(existing_root, desired_root)
                # Ensure we also rename decoupled folders if they exist
                old_base = os.path.basename(existing_root)
                new_base = os.path.basename(desired_root)
                for decoupled in ["metadata", "logs", "archive"]:
                    old_path = os.path.join(OUTPUT_DIR, decoupled, old_base)
                    new_path = os.path.join(OUTPUT_DIR, decoupled, new_base)
                    if os.path.exists(old_path) and not os.path.exists(new_path):
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        os.rename(old_path, new_path)
            patient_report_folder = desired_root if os.path.exists(desired_root) else (existing_root or desired_root)
        except Exception as e:
            print(f"   ⚠️  Could not align patient folder name: {e}")

    # ── 7. VERSION & ARCHIVE ───────────────────────────────────────────────────
    current_major = get_latest_major_version(patient_id)
    if generation_mode["persona"]:
        doc_major_version = current_major + 1
        doc_minor_version = 0
    else:
        doc_major_version = current_major if current_major > 0 else 1
        doc_minor_version = get_document_minor_version(patient_id, doc_major_version)
        
    doc_version_str = f"{doc_major_version}.{doc_minor_version}" if doc_minor_version > 0 else f"{doc_major_version}"
    print(f"   🔖 Document version: v{doc_version_str}")

    if cancel_check and cancel_check():
        print("   ⛔ Cancellation requested before PDF archiving.")
        return None

    # Archive ONLY documents that are about to be overwritten
    archive_patient_files(patient_id, generation_mode, archive_token=archive_token)

    # ── 8. WRITE DOCUMENTS ─────────────────────────────────────────────────────
    current_year = datetime.datetime.now().year
    current_mrn  = f"MRN-{patient_id}-{current_year}"
    docs_written: list[str] = []

    if not patient_report_folder:
        patient_report_folder = get_patient_report_folder(patient_id, p_full_name)
    # Ensure the patient's report sub-folder exists before writing
    os.makedirs(patient_report_folder, exist_ok=True)

    # ── 8a. PERSONA ────────────────────────────────────────────────────────────
    if generation_mode["persona"] and result.patient_persona:
        persona_path = pdf_generator.create_persona_pdf(
            patient_id,
            p_full_name,
            result.patient_persona,
            filtered_documents,
            image_map=None,
            mrn=current_mrn,
            output_folder=get_patient_persona_folder(patient_id),
            version=doc_version_str,
        )
        pf = os.path.basename(persona_path)
        docs_written.append(pf)
        print(f"   👤 Persona → {pf}")

    # ── 8b. REPORTS ────────────────────────────────────────────────────────────
    if generation_mode["reports"] and filtered_documents:
        # Load template sections for template-driven PDF ordering (intensive PDF fix)
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        loaded_template_sections = []
        for tmpl_file in document_plan.get("document_templates", []):
            tmpl_path = os.path.join(templates_dir, tmpl_file)
            if os.path.exists(tmpl_path):
                try:
                    with open(tmpl_path, "r", encoding="utf-8") as f:
                        loaded_template_sections.append(json.load(f).get("sections", []))
                except Exception:
                    loaded_template_sections.append([])
            else:
                loaded_template_sections.append([])

        persist_images = os.getenv("PERSIST_IMAGES", "false").lower() == "true"
        print(f"   📄 Generating {len(filtered_documents)} report(s) at v{doc_version_str}…")
        for seq, doc in enumerate(filtered_documents, start=1):
            if cancel_check and cancel_check():
                print("   ⛔ Cancellation requested during PDF generation loop.")
                return None
            try:
                seq_str            = f"{seq:03d}"
                doc_identifier     = f"DOC-{patient_id}-v{doc_version_str}-{seq_str}"
                safe_title_hint = sanitize_filename_component(getattr(doc, "title_hint", "document"))
                final_filename_base = f"{doc_identifier}-{safe_title_hint}"

                is_valid, errors = validate_structure(doc.content)
                if not is_valid:
                    print(f"      ⚠️  '{doc.title_hint}' invalid: {errors}. Attempting AI fix…")
                    doc.content = ai_engine.fix_document_content(doc.content, errors)
                    is_valid, errors = validate_structure(doc.content)
                    if not is_valid:
                        print(f"      ❌ Fix failed. Marking as NAF.")
                        final_filename_base += "-NAF"
                    else:
                        print(f"      ✅ AI fixed the document.")

                # V3 Architecture formatting
                formatted_content = doc.content
                try:
                    if isinstance(doc.content, dict):
                        structured_data = doc.content
                    else:
                        structured_data = json.loads(doc.content)
                    
                    provider_obj = result.patient_persona.provider if result.patient_persona else None
                    pa_request = getattr(result.patient_persona, "pa_request", None) if result.patient_persona else None
                    provider_name = (
                        getattr(pa_request, "requesting_provider", None)
                        or getattr(provider_obj, "generalPractitioner", None)
                        or "Unknown"
                    )
                    provider_address = getattr(provider_obj, "address", "N/A") if provider_obj else "N/A"
                    provider_phone = getattr(provider_obj, "phone", "N/A") if provider_obj else "N/A"

                    facility_obj = getattr(result.patient_persona, "procedure_facility", None) if result.patient_persona else None
                    facility_name = (
                        getattr(facility_obj, "facility_name", None)
                        or getattr(provider_obj, "managingOrganization", None)
                        or "Diagnostic Center"
                    )
                    
                    patient_phone = result.patient_persona.telecom if result.patient_persona else "N/A"
                    payer_obj = result.patient_persona.payer if result.patient_persona else None
                    plan_type = getattr(payer_obj, "plan_type", "N/A") if payer_obj else "N/A"

                    metadata = {
                        "patient_id": patient_id,
                        "mrn": current_mrn,
                        "patient_name": p_full_name or "Unknown",
                        "dob": result.patient_persona.dob if result.patient_persona else "",
                        "gender": result.patient_persona.gender if result.patient_persona else "",
                        "patient_phone": patient_phone,
                        "report_date": datetime.datetime.now().strftime("%m-%d-%Y"),
                        "provider": provider_name,
                        "provider_address": provider_address,
                        "provider_phone": provider_phone,
                        "facility": facility_name,
                        "accession_id": f"ACC-{patient_id}-{seq_str}",
                        "doc_type": doc.title_hint,
                        "plan_type": plan_type
                    }
                    template_sections = (
                        loaded_template_sections[min(seq - 1, len(loaded_template_sections) - 1)]
                        if loaded_template_sections
                        else None
                    )
                    formatted_content = format_clinical_document(
                        metadata, structured_data, ordered_sections_override=template_sections
                    )
                    # Optional: minimum content depth check (intensive PDF)
                    body_start = formatted_content.find("\n[")
                    body_content = formatted_content[body_start:].strip() if body_start >= 0 else formatted_content
                    if len(body_content) < 200:
                        print(f"      ⚠️  Document '{doc.title_hint}' may be sparse ({len(body_content)} chars); consider regenerating with feedback for more intensive output.")
                except Exception as e:
                    print(f"      ⚠️  Could not format JSON natively, defaulting to AI output text: {e}")

                image_path = None
                imaging_keywords = ["ECG", "XRAY", "X-RAY", "MRI", "CT", "ULTRASOUND", "ECHO", "RADIOGRAPH", "SCAN"]
                # Use regex with word boundaries to avoid 'CT' matching 'ACTION'
                found_keyword = next((kw for kw in imaging_keywords if re.search(rf'\b{kw}\b', str(doc.title_hint).upper())), "Radiograph")
                
                if any(re.search(rf'\b{kw}\b', str(doc.title_hint).upper()) for kw in imaging_keywords):
                    print(f"      📸 Imaging document detected '{doc.title_hint}', generating supportive AI visual...")
                    img_filename = f"{final_filename_base}_img.png"
                    temp_image_path = os.path.join(patient_report_folder, img_filename)
                    
                    # Provide a sanitized, high-fidelity context instead of raw JSON
                    sanitized_hint = doc.title_hint.replace("_", " ").replace("-", " ")
                    image_context = f"High-fidelity medical visualization of {sanitized_hint} radiological findings"
                    
                    generated_path = ai_engine.generate_clinical_image(
                        context=image_context, 
                        image_type=found_keyword, 
                        output_path=temp_image_path
                    )
                    
                    if generated_path:
                        image_path = generated_path
                        print(f"      🖼️  Saved image to {image_path}")

                pdf_path = pdf_generator.create_patient_pdf(
                    patient_id=patient_id,
                    doc_type=final_filename_base,
                    content=formatted_content,
                    patient_persona=result.patient_persona,
                    doc_metadata=doc,
                    base_output_folder=patient_report_folder,
                    image_path=image_path,
                    version=doc_version_str,
                )
                if image_path and not persist_images:
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        print(f"      ⚠️  Could not remove temp image {image_path}: {e}")
                rf = os.path.basename(pdf_path)
                docs_written.append(rf)
                print(f"      ✅ {rf}")
            except Exception as e:
                
                print(f"      ❌ Report generation failed for '{getattr(doc, 'title_hint', 'Unknown')}'. Error: {e}")
                print(traceback.format_exc())
                continue

    # ── 8c. SUMMARY ────────────────────────────────────────────────────────────
    if generation_mode["summary"]:
        if cancel_check and cancel_check():
            print("   ⛔ Cancellation requested before summary generation.")
            return None
        try:
            print(f"   📋 Generating annotator summary at v{doc_version_str}…")

            search_results      = None
            verification_notes  = []
            procedure_text      = case_data.get("procedure", "")
            has_excel_procedure = (
                procedure_text
                and str(procedure_text) != "nan"
                and str(procedure_text).strip()
            )

            if not has_excel_procedure:
                verification_notes.append(
                    "⚠️ Procedure information missing from Excel — verify CPT code manually"
                )

            try:
                from src.ai.search_engine import MedicalSearchEngine
                search_engine = MedicalSearchEngine()
                if search_engine.enabled and not has_excel_procedure:
                    details_text = case_data.get("details", "")
                    if details_text:
                        cpt_match = re.search(r"CPT[:\s]*(\d{5})", str(details_text), re.IGNORECASE)
                        if cpt_match:
                            cpt_info = search_engine.search_cpt_code(cpt_match.group(1))
                            if cpt_info and cpt_info.description and len(cpt_info.description) > 20:
                                search_results = {
                                    "cpt_info": {
                                        "code": cpt_info.code,
                                        "description": cpt_info.description,
                                        "source_url": cpt_info.source_url,
                                    }
                                }
            except Exception:
                pass

            if verification_notes:
                search_results = search_results or {}
                search_results["verification_notes"] = verification_notes

            documents_for_summary = filtered_documents if generation_mode["reports"] else None

            # Generate Concise Summary
            concise_summary = ai_engine.generate_concise_summary(
                case_details=case_data,
                patient_persona=result.patient_persona,
                generated_documents=documents_for_summary,
                search_results=search_results,
            )
            con_path = pdf_generator.create_concise_summary_pdf(
                patient_id=patient_id,
                concise_summary=concise_summary,
                case_details=case_data,
                patient_persona=result.patient_persona,
                output_folder=get_patient_summary_folder(patient_id),
                version=doc_version_str,
            )
            if con_path:
                sf = os.path.basename(con_path)
                docs_written.append(sf)
                print(f"   📊 Summary → {sf}")
            else:
                print("   ⚠️  Summary creation returned no path.")

        except Exception as e:
            print(f"   ⚠️  Summary generation failed: {e}")

    # ── 9. PATIENT TEXT RECORD ─────────────────────────────────────────────────
    if result.patient_persona:
        if cancel_check and cancel_check():
            print("   ⛔ Cancellation requested before writing patient record.")
            return None
        try:
            rec_path = patient_record_writer.write_patient_record(
                patient_id=patient_id,
                persona=result.patient_persona,
                version=doc_version_str,
                docs_generated=docs_written,
                feedback=feedback,
            )
            print(f"   📝 Patient record updated: {os.path.basename(rec_path)}")
        except Exception as e:
            print(f"   ⚠️  Patient record write failed: {e}")

    print(f"\n✅ Workflow complete for patient {patient_id}. {len(docs_written)} document(s) written.")
    return p_full_name

def preview_patient_generation(
    patient_id: str,
    feedback: str = "",
    excluded_names: list[str] = None,
    generation_mode: dict = None,
    cancel_check: callable = None,
    generate_rejection_docs: bool = False,
) -> dict | None:
    """
    Run AI generation for a patient WITHOUT writing any PDFs.
    Returns a JSON-serialisable payload dict for the preview UI.
    """
    if excluded_names is None:
        excluded_names = []
    if generation_mode is None:
        generation_mode = {"persona": True, "reports": True, "summary": False}

    generation_mode = {
        "persona": generation_mode.get("persona", True),
        "reports": generation_mode.get("reports", True),
        "summary": False,   # summary is deferred until PDF confirm
    }

    print(f"\n🔍 Preview generation for Patient ID: {patient_id}")
    case_data = data_loader.load_patient_case(patient_id)
    if not case_data:
        print(f"❌ Patient ID '{patient_id}' not found in Excel plan.")
        return None

    history_txt = history_manager.get_history(patient_id)
    existing_patient = patient_db.load_patient(patient_id)
    has_persona = bool(existing_patient and (existing_patient.get("first_name") or existing_patient.get("last_name")))
    patient_state = state_manager.build_patient_state(patient_id, case_data)
    document_plan = document_planner.create_and_save_document_plan(patient_id, case_data)

    if cancel_check and cancel_check():
        print("   ⛔ Cancellation requested before AI preview generation.")
        return None

    feedback = _augment_feedback_with_risk_assessment(feedback, case_details=case_data)
    try:
        result, _usage = ai_engine.generate_clinical_data(
            case_details=case_data,
            patient_state=patient_state,
            document_plan=document_plan,
            user_feedback=feedback,
            history_context=history_txt,
            existing_persona=existing_patient if has_persona else None,
        )
    except Exception as e:
        print(f"❌ AI generation failed: {e}")
        return None

    # Persist persona to DB so PDF rendering later has the correct identity
    if result.patient_persona:
        patient_db.save_patient(patient_id, result.patient_persona.model_dump())

    # Serialise to plain JSON
    docs_serialised = []
    for doc in (result.documents or []):
        docs_serialised.append({
            "title_hint": getattr(doc, "title_hint", "Clinical Document"),
            "content": doc.content if isinstance(doc.content, dict) else str(doc.content),
            "date": getattr(doc, "date", ""),
        })

    payload = {
        "patient_persona": result.patient_persona.model_dump() if result.patient_persona else {},
        "documents": docs_serialised,
        "changes_summary": result.changes_summary,
    }
    print(f"✅ Preview ready: {len(docs_serialised)} document(s)")
    return payload

def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")

def _html_to_sectioned_text(content_html: str) -> str:
    """
    Convert editor HTML into a deterministic, PDF-friendly plain-text format
    with optional [SECTION] headings. This preserves structure without relying
    on HTML rendering in ReportLab.
    """
    if not content_html:
        return ""

    text = content_html

    # Headings to [SECTION] markers
    def _heading_repl(match):
        heading = _strip_html_tags(match.group(1))
        heading = html_lib.unescape(heading)
        heading = re.sub(r"\s+", " ", heading).strip()
        if not heading:
            return ""
        label = heading.upper().replace(" ", "_")
        return f"\n[{label}]\n"

    text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", _heading_repl, text, flags=re.IGNORECASE | re.DOTALL)

    # Lists and line breaks
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(ul|ol)\s*>", "\n", text, flags=re.IGNORECASE)

    # Strip remaining tags, unescape entities
    text = _strip_html_tags(text)
    text = html_lib.unescape(text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def render_patient_pdfs_from_content(
    patient_id: str,
    generation_mode: dict,
    documents_content: list,   # [{title_hint, content_html}]
    persona_json: dict | None = None,
    summarize: bool = True,
    cancel_check: callable = None,
    archive_token: str = None,
) -> list[str]:
    """
    Write PDFs from user-confirmed (possibly edited) content.
    Skips AI re-generation — content is rendered directly.
    Returns list of written filenames.
    """
    

    docs_written: list[str] = []
    current_year = datetime.datetime.now().year
    current_mrn = f"MRN-{patient_id}-{current_year}"
    
    current_major = get_latest_major_version(patient_id)
    if generation_mode.get("persona", False):
        doc_major_version = current_major + 1
        doc_minor_version = 0
    else:
        doc_major_version = current_major if current_major > 0 else 1
        doc_minor_version = get_document_minor_version(patient_id, doc_major_version)
        
    doc_version_str = f"{doc_major_version}.{doc_minor_version}" if doc_minor_version > 0 else f"{doc_major_version}"

    # Reconstruct persona Pydantic object
    persona_obj = None
    source = persona_json or patient_db.load_patient(patient_id)
    if source:
        try:
            from src.ai.models import PatientPersona
            persona_obj = PatientPersona(**source)
        except Exception as e:
            print(f"   ⚠️  Persona reconstruction failed: {e}")

    case_data = None
    try:
        case_data = data_loader.load_patient_case(patient_id)
    except Exception:
        pass

    # Apply insurance overrides even when rendering from existing persona
    patient_state = None
    try:
        patient_state = state_manager.build_patient_state(patient_id, case_data or {})
    except Exception:
        patient_state = None
    _apply_insurance_overrides(persona_obj, patient_state)

    p_full_name = (
        f"{persona_obj.first_name} {persona_obj.last_name}" if persona_obj
        else f"Patient_{patient_id}"
    )

    # Ensure patient output folder uses "ID - Name" convention when possible
    patient_report_folder = None
    if persona_obj:
        try:
            from .core.config import find_patient_folder, get_patient_root
            existing_root = find_patient_folder(patient_id)
            desired_root = get_patient_root(patient_id, p_full_name, prefer_name=True)
            if existing_root and existing_root != desired_root and not os.path.exists(desired_root):
                os.rename(existing_root, desired_root)
            patient_report_folder = desired_root if os.path.exists(desired_root) else (existing_root or desired_root)
        except Exception as e:
            print(f"   ⚠️  Could not align patient folder name: {e}")

    if cancel_check and cancel_check():
        print("   ⛔ Cancellation requested before archiving files.")
        return []

    archive_patient_files(patient_id, generation_mode, archive_token=archive_token)
    if not patient_report_folder:
        patient_report_folder = get_patient_report_folder(patient_id, p_full_name)
    os.makedirs(patient_report_folder, exist_ok=True)

    # ── Persona PDF ───────────────────────────────────────────────────────────
    if generation_mode.get("persona", False) and persona_obj:
        try:
            persona_path = pdf_generator.create_persona_pdf(
                patient_id, p_full_name, persona_obj, [],
                image_map=None, mrn=current_mrn,
                output_folder=get_patient_persona_folder(patient_id), version=doc_version_str,
            )
            docs_written.append(os.path.basename(persona_path))
            print(f"   👤 Persona → {os.path.basename(persona_path)}")
        except Exception as e:
            print(f"   ⚠️  Persona PDF failed: {e}")

    # ── Report PDFs from edited content ──────────────────────────────────────
    if generation_mode.get("reports", False) and documents_content:
        for seq, doc_info in enumerate(documents_content, start=1):
            if cancel_check and cancel_check():
                print("   ⛔ Cancellation requested during PDF creation.")
                return []
            try:
                title_hint = doc_info.get("title_hint", f"Document_{seq}")
                content_html = doc_info.get("content_html", "")
                content_body = _html_to_sectioned_text(content_html)
                if not content_body and content_html:
                    # Fallback: best-effort plain text
                    content_body = _strip_html_tags(content_html).strip()
                seq_str = f"{seq:03d}"
                doc_identifier = f"DOC-{patient_id}-v{doc_version_str}-{seq_str}"
                safe_title = sanitize_filename_component(title_hint)
                final_base = f"{doc_identifier}-{safe_title}"

                fac_name = "Medical Center"
                if persona_obj:
                    proc_fac = getattr(persona_obj, "procedure_facility", None)
                    if proc_fac:
                        fac_name = getattr(proc_fac, "facility_name", "Medical Center")

                prov_name = "Unknown Provider"
                if persona_obj and getattr(persona_obj, "provider", None):
                    prov_name = getattr(persona_obj.provider, "generalPractitioner", "Unknown Provider")

                doc_meta = types.SimpleNamespace(
                    title_hint=title_hint,
                    facility_name=fac_name,
                    provider_name=prov_name,
                    service_date=datetime.datetime.now().strftime("%m-%d-%Y"),
                    accession_number=f"ACC-{patient_id}-{seq_str}",
                )
                image_path = None
                imaging_keywords = ["ECG", "XRAY", "X-RAY", "MRI", "CT", "ULTRASOUND", "ECHO", "RADIOGRAPH", "SCAN"]
                found_keyword = next((kw for kw in imaging_keywords if re.search(rf'\b{kw}\b', str(title_hint).upper())), "Radiograph")
                
                if any(re.search(rf'\b{kw}\b', str(title_hint).upper()) for kw in imaging_keywords):
                    print(f"      📸 Imaging document detected '{title_hint}', generating supportive AI visual...")
                    img_filename = f"{final_base}_img.png"
                    temp_image_path = os.path.join(patient_report_folder, img_filename)
                    
                    sanitized_hint = title_hint.replace("_", " ").replace("-", " ")
                    image_context = f"High-fidelity medical visualization of {sanitized_hint} radiological findings"
                    
                    try:
                        from src.ai.engine import AIEngine
                        ai_engine = AIEngine()
                        generated_path = ai_engine.generate_clinical_image(
                            context=image_context, 
                            image_type=found_keyword, 
                            output_path=temp_image_path
                        )
                        if generated_path:
                            image_path = generated_path
                            print(f"      🖼️  Saved image to {image_path}")
                    except Exception as e:
                        print(f"      ⚠️  Could not generate image: {e}")

                pdf_path = pdf_generator.create_patient_pdf(
                    patient_id=patient_id,
                    doc_type=final_base,
                    content=content_body,
                    patient_persona=persona_obj,
                    doc_metadata=doc_meta,
                    base_output_folder=patient_report_folder,
                    image_path=image_path,
                    version=doc_version_str,
                )
                
                if image_path:
                    persist_images = os.getenv("PERSIST_IMAGES", "false").lower() == "true"
                    if not persist_images:
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            print(f"      ⚠️  Could not remove temp image {image_path}: {e}")

                docs_written.append(os.path.basename(pdf_path))
                print(f"      ✅ {os.path.basename(pdf_path)}")
            except Exception as e:
                
                print(f"      ❌ PDF failed for '{doc_info.get('title_hint','?')}': {e}")
                print(traceback.format_exc())

    # ── Summary PDF ───────────────────────────────────────────────────────────
    if summarize and generation_mode.get("summary", False) and case_data and persona_obj:
        if cancel_check and cancel_check():
            print("   ⛔ Cancellation requested before generating summary.")
            return []
        try:
            concise_summary = ai_engine.generate_concise_summary(
                case_details=case_data,
                patient_persona=persona_obj,
                generated_documents=None,
                search_results=None,
            )
            sum_path = pdf_generator.create_concise_summary_pdf(
                patient_id=patient_id,
                concise_summary=concise_summary,
                case_details=case_data,
                patient_persona=persona_obj,
                output_folder=get_patient_summary_folder(patient_id),
                version=doc_version_str,
            )
            if sum_path:
                docs_written.append(os.path.basename(sum_path))
                print(f"   📊 Summary → {os.path.basename(sum_path)}")
        except Exception as e:
            print(f"   ⚠️  Summary failed: {e}")

    print(f"\n✅ {len(docs_written)} PDF(s) rendered from confirmed content.")
    return docs_written
