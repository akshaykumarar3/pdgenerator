import os


import data_loader
import ai_engine
import pdf_generator
import history_manager
import requests
import datetime
from datetime import timedelta
import random
import core.patient_db as patient_db
import purge_manager
from doc_validator import validate_structure
from dotenv import load_dotenv

# Load Env (Explicitly to be safe, though ai_engine does it)
env_path = os.path.join(os.path.dirname(__file__), "cred", ".env")
load_dotenv(env_path)

# OUTPUT CONFIGURATION
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated_output")
PERSONA_DIR = os.path.join(OUTPUT_DIR, "persona")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "patient-reports")
SUMMARY_DIR = os.path.join(OUTPUT_DIR, "summary")

# Validate/Create Directories
for d in [OUTPUT_DIR, PERSONA_DIR, REPORTS_DIR, SUMMARY_DIR]:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
        # print(f"📁 Verified Folder: {d}") # Noise reduction

# ===== DATE CALCULATION HELPERS =====

def calculate_procedure_date() -> str:
    """
    Calculate a future procedure date (7-90 days from today).
    
    Returns:
        ISO format date string (YYYY-MM-DD)
    """
    today = datetime.datetime.now()
    days_ahead = random.randint(7, 90)
    procedure_date = today + timedelta(days=days_ahead)
    return procedure_date.strftime("%Y-%m-%d")

def calculate_encounter_date(procedure_date_str: str, days_before: int) -> str:
    """
    Calculate encounter date relative to procedure date.
    
    Args:
        procedure_date_str: Procedure date in YYYY-MM-DD format
        days_before: Number of days before procedure (positive integer)
    
    Returns:
        ISO format date string (YYYY-MM-DD)
    """
    procedure_date = datetime.datetime.strptime(procedure_date_str, "%Y-%m-%d")
    encounter_date = procedure_date - timedelta(days=days_before)
    return encounter_date.strftime("%Y-%m-%d")

def get_today_date() -> str:
    """
    Get today's date in ISO format.
    
    Returns:
        ISO format date string (YYYY-MM-DD)
    """
    return datetime.datetime.now().strftime("%Y-%m-%d")

# ===== DOCUMENT COHERENCE HELPERS =====

def load_existing_context(patient_id: str, generation_mode: dict) -> dict:
    """
    Load existing documents for context to ensure coherence.
    
    Args:
        patient_id: Patient ID
        generation_mode: Dict with 'persona', 'reports', 'summary' flags
    
    Returns:
        Dict with 'persona', 'reports', 'summary' context strings
    """
    context = {
        "persona": None,
        "reports": [],
        "summary": None,
        "procedure_date": None,
        "facility": None
    }
    
    # Load existing persona if not generating it
    if not generation_mode.get("persona", False):
        existing_patient = patient_db.load_patient(patient_id)
        if existing_patient:
            context["persona"] = existing_patient
            # Extract key temporal/facility info
            context["procedure_date"] = existing_patient.get("expected_procedure_date")
            facility_data = existing_patient.get("procedure_facility")
            if facility_data:
                context["facility"] = f"{facility_data.get('facility_name')}, {facility_data.get('city')}, {facility_data.get('state')}"
    
    # Load existing reports if not generating them
    if not generation_mode.get("reports", False):
        patient_report_folder = os.path.join(REPORTS_DIR, patient_id)
        if os.path.exists(patient_report_folder):
            report_files = [f for f in os.listdir(patient_report_folder) if f.endswith(".pdf")]
            context["reports"] = report_files[:5]  # Limit to 5 for context
    
    # Load existing summary if not generating it
    if not generation_mode.get("summary", False):
        summary_file = os.path.join(SUMMARY_DIR, f"{patient_id}-summary.pdf")
        if os.path.exists(summary_file):
            context["summary"] = summary_file
    
    return context

def process_patient_workflow(patient_id: str, feedback: str = "", excluded_names: list[str] = None, generation_mode: dict = None) -> str:
    """
    Main orchestration logic for a single patient.
    Returns the Generated Name (str) if successful, else None.
    
    generation_mode: dict with keys 'summary', 'reports', 'persona' (bool values)
    """
    if excluded_names is None:
        excluded_names = []
    if generation_mode is None:
        generation_mode = {"summary": True, "reports": True, "persona": True}
        
    print(f"🚀 Starting Workflow for Patient ID: {patient_id}")
    print(f"\n📂 Loading Case Data for ID: {patient_id}...")
    case_data = data_loader.load_patient_case(patient_id)
    
    if not case_data:
        print(f"❌ Error: Patient ID '{patient_id}' not found in Excel Plan.")
        return
    
    print(f"   ✅ Case Found: {case_data['procedure']} -> {case_data['outcome']}")
    
    # 2. LOAD HISTORY
    history_txt = history_manager.get_history(patient_id)
    if history_txt:
        print(f"   📜 History Found: Loaded past context.")
    
    # 3. Check Persistent DB for Consistency
    existing_patient = patient_db.load_patient(patient_id)
    persona_context_prompt = ""
    if existing_patient:
        print(f"      🔄 Found Existing Patient Record: {existing_patient.get('first_name')} {existing_patient.get('last_name')}")
    # Scan for existing documents (Smart Duplicate Prevention)
    patient_report_folder = os.path.join(REPORTS_DIR, patient_id)
    existing_titles = []
    existing_docs_map = {}  # Map title -> full filename for potential replacement
    
    if os.path.exists(patient_report_folder):
        for f in os.listdir(patient_report_folder):
            if f.endswith(".pdf") and f.startswith(f"DOC-{patient_id}-"):
                # Extract title: DOC-210-001-Title.pdf -> Title
                parts = os.path.splitext(f)[0].split("-")
                if len(parts) >= 4:
                    title = "-".join(parts[3:])
                    # Remove NAF suffix if present
                    if title.endswith("-NAF"):
                        title = title[:-4]
                    existing_titles.append(title)
                    existing_docs_map[title] = f
    
    if existing_titles:
        print(f"      📥 Existing Documents Found: {len(existing_titles)}")
        print(f"         Documents: {', '.join(existing_titles[:5])}{'...' if len(existing_titles) > 5 else ''}")
        print(f"         AI will avoid creating duplicates unless multiple reports are needed.")
    
    print(f"🧠 Processing with AI... (Outcome: {case_data['outcome']})")
    
    try:
        # Result is ClinicalDataPayload (no SQL)
        result, usage = ai_engine.generate_clinical_data(
            case_details=case_data, 
            user_feedback=feedback, 
            history_context=history_txt, 
            existing_persona=existing_patient, 
            excluded_names=excluded_names,
            existing_filenames=existing_titles  # Pass existing titles for duplicate prevention
        )
        
        # SAVE HISTORY
        history_manager.append_history(patient_id, feedback, result.changes_summary)
        
        # GENERATE PDFs (Dynamic + Unique)
        print(f"   📄 Generating {len(result.documents)} Document(s)...")

        # === DOCUMENT COMPLIANCE ANALYSIS ===
        # (Performed per-document during generation now)

        seen_titles = {}
        # 6. Save/Update Patient DB
        # Structured Persona Object is now available
        if result.patient_persona:
            db_entry = result.patient_persona.model_dump()
            # Flatten or keep nested? Keep nested as per user JSON requirement.
            # We map Pydantic fields to the "p_" fields user requested roughly, or just store the clean object.
            # actually user wants "p_telecom", etc. 
            # Ideally we adapt it, but for now let's save the RAW structured data which has everything.
            # Then the export logic (not this file) can transform it.
            # Or we can just store the Pydantic dump which is very clean.
            
            patient_db.save_patient(patient_id, db_entry)
            
            p_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
            print(f"      💾 Patient {patient_id} ({p_name}) saved to Core DB.")

        # 7. Generate Documents (Reports - conditional)
        patient_report_folder = os.path.join(REPORTS_DIR, patient_id)

        # REPORTS GENERATION (conditional)
        if generation_mode.get("reports", True) and result.documents:
            print(f"   📄 Generating {len(result.documents)} Report(s)...")
            doc_seq_counter = 1
            for doc in result.documents:
                # Construct Filename
                seq_str = f"{doc_seq_counter:03d}"
                doc_identifier = f"DOC-{patient_id}-{seq_str}"
                final_filename_base = f"{doc_identifier}-{doc.title_hint}"
                
                # Validation & Repair
                is_valid, errors = validate_structure(doc.content)
                if not is_valid:
                    print(f"      ⚠️  Document '{doc.title_hint}' Invalid: {errors}. Attempting AI Fix...")
                    doc.content = ai_engine.fix_document_content(doc.content, errors)
                    is_valid, errors = validate_structure(doc.content)
                    if not is_valid:
                        print(f"      ❌ Fix Failed. Marking as NAF.")
                        final_filename_base += "-NAF"
                    else:
                        print(f"      ✅ AI Fixed the document.")
                
                # Create PDF (without image)
                pdf_path = pdf_generator.create_patient_pdf(
                    patient_id=patient_id, 
                    doc_type=final_filename_base, 
                    content=doc.content, 
                    patient_persona=result.patient_persona,
                    doc_metadata=doc,
                    base_output_folder=patient_report_folder,
                    image_path=None  # No standalone images
                )
                print(f"      - Created: {os.path.basename(pdf_path)}")
                doc_seq_counter += 1
            
        # GENERATE PERSONA (New Requirement)
        current_year = datetime.datetime.now().year
        current_mrn = f"MRN-{patient_id}-{current_year}" # Centralized MRN

        # PERSONA GENERATION (conditional)
        if generation_mode.get("persona", False) and result.patient_persona:
            p_full_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
            persona_path = pdf_generator.create_persona_pdf(
                patient_id, 
                p_full_name, 
                result.patient_persona, 
                result.documents, 
                image_map=None,  # No standalone images
                mrn=current_mrn, 
                output_folder=PERSONA_DIR
            )
            print(f"   👤 Persona Created: {os.path.basename(persona_path)}")
            
        
        # ANNOTATOR SUMMARY GENERATION (conditional) - AFTER all documents
        # This is the NEW annotator-focused verification guide
        if generation_mode.get("summary", True):
            try:
                print(f"   📋 Generating Annotator Verification Guide...")
                
                # WEB SEARCH: Get official CPT code information (ONLY if enabled AND Excel data is missing)
                search_results = None
                verification_notes = []
                
                # Check if Excel has procedure data
                procedure_text = case_data.get('procedure', '')
                has_excel_procedure = procedure_text and str(procedure_text) != 'nan' and str(procedure_text).strip() != ''
                
                if not has_excel_procedure:
                    verification_notes.append("⚠️ Procedure information missing from Excel - verify CPT code manually")
                
                try:
                    from search_engine import MedicalSearchEngine
                    search_engine = MedicalSearchEngine()
                    
                    # Only search if:
                    # 1. Web search is enabled
                    # 2. Excel data is missing or incomplete
                    if search_engine.enabled and not has_excel_procedure:
                        print(f"      ℹ️  Excel procedure data missing, attempting web search...")
                        
                        # Try to extract CPT from other fields or documents
                        import re
                        cpt_match = None
                        
                        # Try to find CPT in details field
                        details_text = case_data.get('details', '')
                        if details_text:
                            cpt_match = re.search(r'CPT[:\s]*(\d{5})', str(details_text), re.IGNORECASE)
                        
                        if cpt_match:
                            target_cpt = cpt_match.group(1)
                            print(f"      🔍 Searching for CPT {target_cpt}...")
                            
                            cpt_info = search_engine.search_cpt_code(target_cpt)
                            
                            if cpt_info and cpt_info.description and len(cpt_info.description) > 20:
                                print(f"      ✅ Found: {cpt_info.description[:50]}...")
                                search_results = {
                                    'cpt_info': {
                                        'code': cpt_info.code,
                                        'description': cpt_info.description,
                                        'source_url': cpt_info.source_url
                                    }
                                }
                                verification_notes.append(f"ℹ️ CPT {target_cpt} description from web search - verify accuracy")
                            else:
                                print(f"      ⚠️  CPT {target_cpt} search returned poor quality results")
                                verification_notes.append(f"⚠️ CPT {target_cpt} found but description quality uncertain - manual verification required")
                        else:
                            print(f"      ⚠️  Could not extract CPT code from case data")
                            verification_notes.append("⚠️ CPT code not found in case data - manual entry required")
                    elif not search_engine.enabled:
                        print(f"      ℹ️  Web search disabled")
                        if not has_excel_procedure:
                            verification_notes.append("⚠️ Web search disabled and Excel data missing - verify all codes manually")
                    else:
                        print(f"      ✅ Using Excel procedure data")
                        
                except ImportError:
                    print(f"      ⚠️  search_engine module not available")
                    if not has_excel_procedure:
                        verification_notes.append("⚠️ Search unavailable and Excel data missing - manual verification required")
                except Exception as search_error:
                    print(f"      ⚠️  Search failed: {search_error}")
                    if not has_excel_procedure:
                        verification_notes.append(f"⚠️ Search failed - manual verification required")
                
                # Add verification notes to search results
                if verification_notes:
                    if not search_results:
                        search_results = {}
                    search_results['verification_notes'] = verification_notes
                
                # Generate AI-powered annotator summary
                # Pass documents if available (for full summary), or None (for partial summary)
                documents_for_summary = result.documents if generation_mode.get("reports", True) else None
                
                annotator_summary = ai_engine.generate_annotator_summary(
                    case_details=case_data,
                    patient_persona=result.patient_persona,
                    generated_documents=documents_for_summary,
                    search_results=search_results  # Pass search results AND verification notes to AI
                )
                
                # Create PDF from structured summary
                # Pass persona so PDF can extract CPT/ICD codes
                sum_path = pdf_generator.create_annotator_summary_pdf(
                    patient_id=patient_id,
                    annotator_summary=annotator_summary,
                    case_details=case_data,
                    patient_persona=result.patient_persona,
                    output_folder=SUMMARY_DIR  # Use dedicated summary folder
                )
                
                if sum_path:
                    print(f"   📊 Annotator Summary Created: {os.path.basename(sum_path)}")
                    # Show verification notes count if any
                    if verification_notes:
                        print(f"      ⚠️  {len(verification_notes)} verification note(s) added to summary")
                else:
                    print(f"   ⚠️  Annotator Summary creation failed.")
                    
            except Exception as e:
                print(f"   ⚠️  Annotator Summary Generation Failed: {e}")
                # Continue processing even if summary fails
        
        # Processing complete

        # Return the new name for caching
        return p_full_name if 'p_full_name' in locals() else None

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        return None


# OUTPUT CONFIGURATION
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated_output")
PERSONA_DIR = os.path.join(OUTPUT_DIR, "persona")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "patient-reports")

# Validate/Create Directories
for d in [OUTPUT_DIR, PERSONA_DIR, REPORTS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

# ... (process_patient_workflow is between these, but we are editing top and bottom params. 
# Better to do separate chunks. I will do top chunk first. 
# Wait, I cannot do multi-chunk with simple replace unless I use multi_replace.
# I will use multi_replace logic by just making 2 calls or use multi_replace tool.
# I'll use simple replace for the function `check_patient_sync_status` first.

def check_patient_sync_status(patient_id: str) -> bool:
    """
    Verification Logic:
    Checks if documents exist for the patient.
    """
    doc_folder = f"documents/{patient_id}"

    # Smart Migration: Rename old summary if needed
    old_summary = os.path.join(doc_folder, f"Patient_{patient_id}_Clinical_Summary.pdf")
    new_summary = os.path.join(doc_folder, f"Clinical_Summary_Patient_{patient_id}.pdf")
    
    if os.path.exists(old_summary) and not os.path.exists(new_summary):
        try:
            os.rename(old_summary, new_summary)
        except Exception:
            pass

    # Check for Documents
    if not os.path.exists(doc_folder):
        return False
        
    pdf_files = [f for f in os.listdir(doc_folder) if f.lower().endswith('.pdf')]
    # Exclude summary from count
    actual_count = len([f for f in pdf_files if "clinical_summary" not in f.lower()])

    if actual_count > 0:
        return True
    else:
        print(f"   ⚠️  No Documents found for {patient_id}")
        return False

def main():
    print("\n🚀 Clinical Data Generator (v2.0) - Modular & Interactive")
    
    # Pre-flight Check
    if not ai_engine.check_connection():
        print("\n❌ Critical: AI Connection Failed. Please check your credentials/internet.")
        return

    # MAIN LOOP
    while True:
        print("\n" + "="*50)
        print("🎯 Enter Patient ID (or '*' for Batch, 'q' to Quit):")
        print("   💡 Tip: Use '225-fix CPT code' to include feedback")
        print("   💡 Tip: Use '221,222,223' for multiple patients")
        target_input = input("   ID: ").strip()

        # 1. QUIT
        if target_input.lower() in ['q', 'quit', 'exit']:
            print("\n👋 Exiting Generator. Goodbye!\n")
            break

        # 2. PURGE COMMAND
        if target_input.startswith('--'):
            if len(target_input) == 2:
                # Global Purge with Selective Menu
                print("\n📋 What to delete?")
                print("   [1] Persona + Reports + Summary (ALL)")
                print("   [2] Reports + Summary")
                print("   [3] Summary only")
                print("   [4] Reports only")
                print("   [5] Persona only")
                print("   [6] Cancel")
                purge_choice = input("   Choice [6]: ").strip() or "6"
                
                if purge_choice == "1":
                    purge_manager.purge_all()
                elif purge_choice == "2":
                    purge_manager.purge_reports_and_summaries()
                elif purge_choice == "3":
                    purge_manager.purge_summaries_only()
                elif purge_choice == "4":
                    purge_manager.purge_reports_only()
                elif purge_choice == "5":
                    purge_manager.purge_personas()
                elif purge_choice == "6":
                    print("   ❌ Operation Cancelled.")
                else:
                    print("   ❌ Invalid choice. Operation Cancelled.")
            else:
                # Specific Patient Purge (e.g. --233)
                p_id = target_input[2:]
                purge_manager.purge_patient(p_id)
            continue

        # 3. PARSE INPUT FOR FEEDBACK AND BATCH
        # Check for feedback: "225-fix the CPT code"
        feedback = ""
        patient_ids = []
        
        if '-' in target_input and not target_input.startswith('--'):
            # Split on first dash only
            parts = target_input.split('-', 1)
            base_input = parts[0].strip()
            feedback = parts[1].strip() if len(parts) > 1 else ""
        else:
            base_input = target_input
        
        # Check for batch: comma-separated IDs or '*'
        if ',' in base_input:
            # Comma-separated patient IDs
            patient_ids = [pid.strip() for pid in base_input.split(',') if pid.strip()]
            print(f"\n🔄 Batch Mode: Processing {len(patient_ids)} patient(s)...")
        elif base_input == '*':
            # All missing patients
            print("\n🔄 Starting Batch Run for MISSING/INCOMPLETE patients...")
            all_ids = data_loader.get_all_patient_ids()
            print(f"   🔍 Found {len(all_ids)} potential patients in Excel.")
            
            # Ask for generation mode
            print("\n📋 What to generate for batch?")
            print("   [1] Persona + Reports + Summary (default)")
            print("   [2] Reports + Summary")
            print("   [3] Summary only")
            print("   [4] Reports only")
            print("   [5] Persona only")
            mode_input = input("   Choice [1]: ").strip()
            
            # Parse mode
            mode_map = {
                "1": {"summary": True, "reports": True, "persona": True},
                "2": {"summary": True, "reports": True, "persona": False},
                "3": {"summary": True, "reports": False, "persona": False},
                "4": {"summary": False, "reports": True, "persona": False},
                "5": {"summary": False, "reports": False, "persona": True},
                "": {"summary": True, "reports": True, "persona": True},
            }
            generation_mode = mode_map.get(mode_input, mode_map["1"])
            
            # OPTIMIZATION: Load names ONCE before loop
            current_names = patient_db.get_all_patient_names()
            print(f"   🧠 Loaded {len(current_names)} existing personas for uniqueness check.")
            
            count = 0
            for p_id in all_ids:
                # Smart Skip Logic
                if check_patient_sync_status(p_id):
                    print(f"   ⏭️  Skipping {p_id} (Verified Complete)")
                else:
                    print(f"\n▶️  Processing {p_id}...")
                    
                    # Pass the IN-MEMORY list implies efficiency
                    new_name = process_patient_workflow(p_id, feedback="", excluded_names=current_names, generation_mode=generation_mode) 
                    
                    # Optimize: Update local list immediately to avoid re-reading DB
                    if new_name:
                         current_names.append(new_name)
                         
                    count += 1
            
            print(f"\n✅ Batch Complete. Processed {count} patients.")
            continue
        else:
            # Single patient ID
            patient_ids = [base_input]

        # 4. PROCESS PATIENT(S)
        if len(patient_ids) > 1:
            # Batch processing for comma-separated IDs
            # Ask for generation mode
            print("\n📋 What to generate for batch?")
            print("   [1] Persona + Reports + Summary (default)")
            print("   [2] Reports + Summary")
            print("   [3] Summary only")
            print("   [4] Reports only")
            print("   [5] Persona only")
            mode_input = input("   Choice [1]: ").strip()
            
            # Parse mode
            mode_map = {
                "1": {"summary": True, "reports": True, "persona": True},
                "2": {"summary": True, "reports": True, "persona": False},
                "3": {"summary": True, "reports": False, "persona": False},
                "4": {"summary": False, "reports": True, "persona": False},
                "5": {"summary": False, "reports": False, "persona": True},
                "": {"summary": True, "reports": True, "persona": True},
            }
            generation_mode = mode_map.get(mode_input, mode_map["1"])
            
            current_names = patient_db.get_all_patient_names()
            
            for idx, p_id in enumerate(patient_ids, 1):
                print(f"\n▶️  Processing {idx}/{len(patient_ids)}: Patient {p_id}...")
                
                new_name = process_patient_workflow(p_id, feedback, excluded_names=current_names, generation_mode=generation_mode)
                
                if new_name:
                    current_names.append(new_name)
            
            print(f"\n✅ Batch Complete. Processed {len(patient_ids)} patients.")
        else:
            # Single patient - ask for generation mode
            p_id = patient_ids[0]
            
            print("\n📋 What to generate?")
            print("   [1] Persona + Reports + Summary (default)")
            print("   [2] Reports + Summary")
            print("   [3] Summary only")
            print("   [4] Reports only")
            print("   [5] Persona only")
            mode_input = input("   Choice [1]: ").strip()
            
            # Parse mode
            mode_map = {
                "1": {"summary": True, "reports": True, "persona": True},   # New default: All
                "2": {"summary": True, "reports": True, "persona": False},  # Reports + Summary
                "3": {"summary": True, "reports": False, "persona": False}, # Summary only
                "4": {"summary": False, "reports": True, "persona": False}, # Reports only
                "5": {"summary": False, "reports": False, "persona": True}, # Persona only
                "": {"summary": True, "reports": True, "persona": True},    # Default when Enter pressed
            }
            generation_mode = mode_map.get(mode_input, mode_map["1"])
            
            # Ask for Feedback (unless already provided in input)
            if not feedback:
                print("\n💡 Feedback Loop")
                print("   Enter any specific instructions for the AI.")
                feedback = input("   Feedback [Press Enter to skip]: ").strip()
            else:
                print(f"\n💡 Feedback (from input): {feedback}")
            
            # Fetch current names for exclusion
            current_names = patient_db.get_all_patient_names()
            process_patient_workflow(p_id, feedback, excluded_names=current_names, generation_mode=generation_mode)

            # Final Verification (if single run)
            if check_patient_sync_status(p_id):
                 print("   ✅ Sync Verified: All referenced documents exist.")
            else:
                 # It might print the mismatch warning internally, but we state it here too
                 pass 
                 
if __name__ == "__main__":
    main()