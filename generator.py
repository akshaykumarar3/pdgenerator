import json
import os
import re
import shutil
import random
import datetime
from datetime import timedelta

from dotenv import load_dotenv

import data_loader
import ai_engine
import pdf_generator
import history_manager
import core.patient_db as patient_db
import purge_manager
import patient_record_writer
import state_manager
import document_planner
from doc_validator import validate_structure, format_clinical_document

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

env_path = os.path.join(os.path.dirname(__file__), "cred", ".env")
load_dotenv(env_path)

from core.config import OUTPUT_DIR, PERSONA_DIR, REPORTS_DIR, SUMMARY_DIR, ensure_output_dirs, get_patient_report_folder


# ─── VERSION HELPERS ───────────────────────────────────────────────────────────

def get_persona_version(patient_id: str) -> int:
    """
    Scan the persona directory for existing files for this patient.
    Returns the *next* version number (e.g. if v2 exists → returns 3).
    Returns 1 when no prior versions exist.
    """
    max_v = 0
    prefix = f"{patient_id}-"
    if os.path.isdir(PERSONA_DIR):
        for fname in os.listdir(PERSONA_DIR):
            if fname.startswith(prefix) and fname.endswith(".pdf"):
                m = re.search(r'-v(\d+)', fname)
                if m:
                    max_v = max(max_v, int(m.group(1)))
    return max_v + 1


# ─── ARCHIVE HELPERS ───────────────────────────────────────────────────────────

def _archive_files_in_dir(folder: str, patient_id: str, match_all_pdfs: bool = False):
    """
    Move PDFs belonging to *patient_id* from *folder* into folder/archive/.
    If match_all_pdfs is True every .pdf in the folder is archived (used for
    the patient-specific reports sub-folder which already only contains that
    patient's files).
    """
    if not os.path.isdir(folder):
        return

    archive_dir = os.path.join(folder, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    prefix_patterns = [
        f"{patient_id}-",
        f"DOC-{patient_id}-",
        f"Clinical_Summary_Patient_{patient_id}",
    ]

    moved = 0
    for fname in os.listdir(folder):
        if fname == "archive" or not fname.endswith(".pdf"):
            continue
        if match_all_pdfs or any(fname.startswith(p) for p in prefix_patterns):
            src = os.path.join(folder, fname)
            dst = os.path.join(archive_dir, fname)
            try:
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                print(f"      ⚠️  Archive move failed for {fname}: {e}")

    if moved:
        print(f"      📦 Archived {moved} file(s) from {os.path.basename(folder)}/")


def archive_patient_files(patient_id: str, generation_mode: dict):
    """
    Archive existing patient documents for every doc type that will be
    re-generated in this run.  Only files about to be overwritten are moved.

    Args:
        patient_id:       Patient ID string.
        generation_mode:  Dict with boolean flags 'persona', 'reports', 'summary'.
    """
    if generation_mode.get("persona", False):
        _archive_files_in_dir(PERSONA_DIR, patient_id)

    if generation_mode.get("summary", False):
        _archive_files_in_dir(SUMMARY_DIR, patient_id)

    if generation_mode.get("reports", False):
        # Reports live in a patient-specific sub-folder; archive everything there
        rpt_folder = get_patient_report_folder(patient_id)
        _archive_files_in_dir(rpt_folder, patient_id, match_all_pdfs=True)


# ─── DATE CALCULATION HELPERS ──────────────────────────────────────────────────

def calculate_procedure_date() -> str:
    """Return a future procedure date 7–90 days from today (ISO format)."""
    days_ahead = random.randint(7, 90)
    return (datetime.datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def calculate_encounter_date(procedure_date_str: str, days_before: int) -> str:
    """
    Return an encounter date *days_before* days before *procedure_date_str*.

    Args:
        procedure_date_str: ISO date string (YYYY-MM-DD).
        days_before:        Positive integer.
    """
    procedure_date = datetime.datetime.strptime(procedure_date_str, "%Y-%m-%d")
    return (procedure_date - timedelta(days=days_before)).strftime("%Y-%m-%d")


def get_today_date() -> str:
    """Return today's date in ISO format (YYYY-MM-DD)."""
    return datetime.datetime.now().strftime("%Y-%m-%d")


# ─── DOCUMENT COHERENCE HELPERS ────────────────────────────────────────────────

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
                f for f in os.listdir(patient_report_folder) if f.endswith(".pdf")
            ]
            context["reports"] = report_files[:5]  # cap for prompt size

    # Load existing summary only when we are NOT regenerating it
    if not generation_mode.get("summary", False):
        summary_file = os.path.join(SUMMARY_DIR, f"{patient_id}-summary.pdf")
        if os.path.exists(summary_file):
            context["summary"] = summary_file

    return context


# ─── SYNC / VERIFICATION ───────────────────────────────────────────────────────

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
    if req_persona and os.path.isdir(PERSONA_DIR):
        has_persona = any(
            f.startswith(f"{patient_id}-") and f.endswith(".pdf")
            for f in os.listdir(PERSONA_DIR)
            if f != "archive"
        )

    # Check Reports
    if req_reports:
        rpt_folder = get_patient_report_folder(patient_id)
        if os.path.isdir(rpt_folder):
            has_report = any(
                f.endswith(".pdf")
                for f in os.listdir(rpt_folder)
                if f != "archive"
            )

    # Check Summary
    if req_summary and os.path.isdir(SUMMARY_DIR):
        has_summary = any(
            (f.startswith(f"{patient_id}-") or f.startswith(f"Clinical_Summary_Patient_{patient_id}"))
            and f.endswith(".pdf")
            for f in os.listdir(SUMMARY_DIR)
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


# ─── MAIN WORKFLOW ─────────────────────────────────────────────────────────────

def process_patient_workflow(
    patient_id: str,
    feedback: str = "",
    excluded_names: list[str] = None,
    generation_mode: dict = None,
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
    if existing_patient:
        print(f"   🔄 Existing record: {existing_patient.get('first_name')} {existing_patient.get('last_name')}")

    # ── 4. BUILD PATIENT STATE & DOCUMENT PLAN ─────────────────────────────────
    patient_state = state_manager.build_patient_state(patient_id, case_data)
    document_plan = document_planner.create_and_save_document_plan(patient_id, case_data)
    
    patient_report_folder = get_patient_report_folder(patient_id)
    # ── 5. AI GENERATION ───────────────────────────────────────────────────────
    print(f"\n🧠 Generating with AI… (Outcome: {case_data.get('outcome', '?')})")
    try:
        result, usage = ai_engine.generate_clinical_data(
            case_details=case_data,
            patient_state=patient_state,
            document_plan=document_plan,
            user_feedback=feedback,
            history_context=history_txt,
            existing_persona=existing_patient,
        )
    except Exception as e:
        print(f"❌ AI generation failed: {e}")
        return None

    # Persist history entry regardless of subsequent steps
    history_manager.append_history(patient_id, feedback, result.changes_summary)

    # ── 6. SAVE PATIENT PERSONA TO DB ─────────────────────────────────────────
    p_full_name = None
    if result.patient_persona:
        db_entry = result.patient_persona.model_dump()
        patient_db.save_patient(patient_id, db_entry)
        p_full_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
        print(f"   💾 Patient DB updated: {p_full_name} (ID {patient_id})")

    # ── 7. VERSION & ARCHIVE ───────────────────────────────────────────────────
    doc_version = get_persona_version(patient_id)
    print(f"   🔖 Document version: v{doc_version}")

    # Archive ONLY documents that are about to be overwritten
    archive_patient_files(patient_id, generation_mode)

    # ── 8. WRITE DOCUMENTS ─────────────────────────────────────────────────────
    current_year = datetime.datetime.now().year
    current_mrn  = f"MRN-{patient_id}-{current_year}"
    docs_written: list[str] = []

    # Ensure the patient's report sub-folder exists before writing
    os.makedirs(patient_report_folder, exist_ok=True)

    # ── 8a. PERSONA ────────────────────────────────────────────────────────────
    if generation_mode["persona"] and result.patient_persona:
        persona_path = pdf_generator.create_persona_pdf(
            patient_id,
            p_full_name,
            result.patient_persona,
            result.documents,
            image_map=None,
            mrn=current_mrn,
            output_folder=PERSONA_DIR,
            version=doc_version,
        )
        pf = os.path.basename(persona_path)
        docs_written.append(pf)
        print(f"   👤 Persona → {pf}")

    # ── 8b. REPORTS ────────────────────────────────────────────────────────────
    if generation_mode["reports"] and result.documents:
        # Load template sections for template-driven PDF ordering (intensive PDF fix)
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
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

        print(f"   📄 Generating {len(result.documents)} report(s) at v{doc_version}…")
        for seq, doc in enumerate(result.documents, start=1):
            seq_str            = f"{seq:03d}"
            doc_identifier     = f"DOC-{patient_id}-v{doc_version}-{seq_str}"
            final_filename_base = f"{doc_identifier}-{doc.title_hint}"

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
                structured_data = json.loads(doc.content)
                
                provider_obj = result.patient_persona.provider if result.patient_persona else None
                if provider_obj:
                    provider_str = f"{provider_obj.generalPractitioner} (NPI: {provider_obj.formatted_npi})"
                    provider_address = getattr(provider_obj, "address", "N/A")
                    provider_phone = getattr(provider_obj, "phone", "N/A")
                else:
                    provider_str = "Unknown"
                    provider_address = "N/A"
                    provider_phone = "N/A"
                
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
                    "report_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "provider": provider_str,
                    "provider_address": provider_address,
                    "provider_phone": provider_phone,
                    "facility": "Diagnostic Center",
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
            if any(kw in doc.title_hint.upper() for kw in imaging_keywords):
                print(f"      📸 Imaging document detected '{doc.title_hint}', generating supportive AI visual...")
                img_filename = f"{final_filename_base}_img.png"
                temp_image_path = os.path.join(patient_report_folder, img_filename)
                
                from ai_engine import generate_clinical_image
                # Pass a slice of the document description to guide DALL-E
                image_context = f"Visual supporting document {doc.title_hint}: {doc.content[:500]}"
                generated_path = generate_clinical_image(context=image_context, image_type=doc.title_hint, output_path=temp_image_path)
                
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
                version=doc_version,
            )
            rf = os.path.basename(pdf_path)
            docs_written.append(rf)
            print(f"      ✅ {rf}")

    # ── 8c. SUMMARY ────────────────────────────────────────────────────────────
    if generation_mode["summary"]:
        try:
            print(f"   📋 Generating annotator summary at v{doc_version}…")

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
                from search_engine import MedicalSearchEngine
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

            documents_for_summary = result.documents if generation_mode["reports"] else None
            annotator_summary = ai_engine.generate_annotator_summary(
                case_details=case_data,
                patient_persona=result.patient_persona,
                generated_documents=documents_for_summary,
                search_results=search_results,
            )

            sum_path = pdf_generator.create_annotator_summary_pdf(
                patient_id=patient_id,
                annotator_summary=annotator_summary,
                case_details=case_data,
                patient_persona=result.patient_persona,
                output_folder=SUMMARY_DIR,
                version=doc_version,
            )

            if sum_path:
                sf = os.path.basename(sum_path)
                docs_written.append(sf)
                print(f"   📊 Summary → {sf}")
            else:
                print("   ⚠️  Summary creation returned no path.")

        except Exception as e:
            print(f"   ⚠️  Summary generation failed: {e}")

    # ── 9. PATIENT TEXT RECORD ─────────────────────────────────────────────────
    if result.patient_persona:
        try:
            rec_path = patient_record_writer.write_patient_record(
                patient_id=patient_id,
                persona=result.patient_persona,
                version=doc_version,
                docs_generated=docs_written,
                feedback=feedback,
            )
            print(f"   📝 Patient record updated: {os.path.basename(rec_path)}")
        except Exception as e:
            print(f"   ⚠️  Patient record write failed: {e}")

    print(f"\n✅ Workflow complete for patient {patient_id}. {len(docs_written)} document(s) written.")
    return p_full_name


# ─── CLI ENTRY POINT ───────────────────────────────────────────────────────────

_MODE_MAP = {
    "1": {"persona": True,  "reports": True,  "summary": True},
    "2": {"persona": False, "reports": True,  "summary": True},
    "3": {"persona": False, "reports": False, "summary": True},
    "4": {"persona": False, "reports": True,  "summary": False},
    "5": {"persona": True,  "reports": False, "summary": False},
    "":  {"persona": True,  "reports": True,  "summary": True},
}

_MODE_LABELS = {
    "1": "Persona + Reports + Summary (default)",
    "2": "Reports + Summary",
    "3": "Summary only",
    "4": "Reports only",
    "5": "Persona only",
}


def _prompt_generation_mode() -> dict:
    """Ask the user which document types to generate and return a mode dict."""
    print("\n📋 What to generate?")
    for k, label in _MODE_LABELS.items():
        marker = " (default)" if k == "1" else ""
        print(f"   [{k}] {label}{marker}")
    choice = input("   Choice [1]: ").strip()
    return _MODE_MAP.get(choice, _MODE_MAP[""])


def main():
    print("\n🚀 Clinical Data Generator — Modular & Interactive")

    if not ai_engine.check_connection():
        print("\n❌ AI connection failed. Check credentials/internet.")
        return

    while True:
        print("\n" + "=" * 60)
        print("🎯 Enter Patient ID  (or '*' for batch, 'q' to quit)")
        print("   💡 '225-fix CPT code'  → patient 225 with feedback")
        print("   💡 '221,222,223'       → comma-separated batch")
        target_input = input("   ID: ").strip()

        if not target_input:
            continue

        # ── QUIT ──────────────────────────────────────────────────────────────
        if target_input.lower() in {"q", "quit", "exit"}:
            print("\n👋 Goodbye!\n")
            break

        # ── PARSE FEEDBACK SUFFIX ──────────────────────────────────────────────
        feedback   = ""
        base_input = target_input
        if "-" in target_input and not target_input.startswith("--"):
            parts      = target_input.split("-", 1)
            base_input = parts[0].strip()
            feedback   = parts[1].strip()

        # ── BATCH: ALL PATIENTS ────────────────────────────────────────────────
        if base_input == "*":
            print("\n🔄 Batch mode: all patients…")
            all_ids       = data_loader.get_all_patient_ids()
            generation_mode = _prompt_generation_mode()
            current_names = patient_db.get_all_patient_names()
            processed = 0

            for p_id in all_ids:
                if check_patient_sync_status(p_id, generation_mode):
                    print(f"   ⏭️  Skipping {p_id} (already complete)")
                    continue
                print(f"\n▶️  Processing {p_id}…")
                new_name = process_patient_workflow(
                    p_id,
                    feedback=feedback,
                    excluded_names=current_names,
                    generation_mode=generation_mode,
                )
                if new_name:
                    current_names.append(new_name)
                processed += 1

            print(f"\n✅ Batch complete. Processed {processed} patient(s).")
            continue

        # ── BATCH: COMMA-SEPARATED ────────────────────────────────────────────
        if "," in base_input:
            patient_ids     = [pid.strip() for pid in base_input.split(",") if pid.strip()]
            generation_mode = _prompt_generation_mode()
            current_names   = patient_db.get_all_patient_names()

            for idx, p_id in enumerate(patient_ids, 1):
                print(f"\n▶️  [{idx}/{len(patient_ids)}] Patient {p_id}…")
                new_name = process_patient_workflow(
                    p_id,
                    feedback,
                    excluded_names=current_names,
                    generation_mode=generation_mode,
                )
                if new_name:
                    current_names.append(new_name)

            print(f"\n✅ Batch complete. {len(patient_ids)} patient(s) processed.")
            continue

        # ── SINGLE PATIENT ────────────────────────────────────────────────────
        p_id = base_input
        generation_mode = _prompt_generation_mode()

        if not feedback:
            print("\n💡 Feedback / Instructions (optional — press Enter to skip)")
            feedback = input("   > ").strip()

        current_names = patient_db.get_all_patient_names()
        process_patient_workflow(
            p_id,
            feedback,
            excluded_names=current_names,
            generation_mode=generation_mode,
        )

        if check_patient_sync_status(p_id, generation_mode):
            print("   ✅ Verification: documents present in output directories.")


if __name__ == "__main__":
    main()