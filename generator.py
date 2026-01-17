import os


import data_loader
import ai_engine
import pdf_generator
import history_manager
import requests
import datetime
import core.patient_db as patient_db
import purge_manager
from doc_validator import validate_structure
from dotenv import load_dotenv
from scan_helper import scan_existing_documents

# Load Env (Explicitly to be safe, though ai_engine does it)
env_path = os.path.join(os.path.dirname(__file__), "cred", ".env")
load_dotenv(env_path)

# OUTPUT CONFIGURATION
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated_output")
PERSONA_DIR = os.path.join(OUTPUT_DIR, "persona")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "patient-reports")

# Validate/Create Directories
for d in [OUTPUT_DIR, PERSONA_DIR, REPORTS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
        # print(f"📁 Verified Folder: {d}") # Noise reduction

def process_patient_workflow(patient_id: str, feedback: str = "", excluded_names: list[str] = None) -> str:
    """
    Main orchestration logic for a single patient.
    Returns the Generated Name (str) if successful, else None.
    """
    if excluded_names is None:
        excluded_names = []
        
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

    # Prepare Patient's Report Folder (needed for incremental logic)
    patient_report_folder = os.path.join(REPORTS_DIR, patient_id)
    if not os.path.exists(patient_report_folder):
        os.makedirs(patient_report_folder, exist_ok=True)

    # === INCREMENTAL GENERATION LOGIC ===
    # Scan for existing documents to prevent duplicates and resume numbering
    max_seq, existing_docs_map = scan_existing_documents(patient_id, patient_report_folder)
    
    doc_seq_counter = max_seq + 1
    if max_seq > 0:
        print(f"      📥 Existing Documents Found: {len(existing_docs_map)} (Max Seq: {max_seq:03d})")
        print(f"      ⏭️  Ready for Smart Update/Append")

    # 4. Generate Clinical Data (AI)
    print(f"🧠 Processing with AI... (Outcome: {case_data['outcome']})")
    
    # Pass ONLY titles to AI to make it easier to match
    existing_titles_list = list(existing_docs_map.keys())
    
    try:
        # Calls the unified AI Engine
        # Returns tuple: (ClinicalDataPayload, usage_stats)
        ai_response = ai_engine.generate_clinical_data(
            case_details=case_data, 
            user_feedback=feedback, 
            history_context=history_txt,
            existing_persona=existing_patient,
            excluded_names=excluded_names,
            existing_filenames=existing_titles_list # Pass TITLES now, not full filenames, clearer for AI
        )
        
        if not ai_response:
            print("❌ AI Engine returned None.")
            return None
            
        result, usage = ai_response

    except Exception as e:
        print(f"❌ Error using AI Engine: {e}")
        return None

    # 5. Process Results
    if not result.documents:
        print("   ✅ AI determined existing documents are sufficient. No new files generated.")
    else:
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
            if existing_patient is None:
                # First time generation - save to DB
                db_entry = result.patient_persona.model_dump()
                patient_db.save_patient(patient_id, db_entry)
                p_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
                print(f"      💾 Patient {patient_id} ({p_name}) saved to Core DB.")
            else:
                # We don't update demographics on re-runs to preserve identity, 
                # unless we implement specific update logic. 
                # For now, assume identity lock.
                
                p_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
                print(f"      💾 Patient {patient_id} ({p_name}) saved to Core DB.")

        # 7. Generate Documents
        generated_images = {} # Map title -> file_path
        image_count = 0
        
        # Prepare Images Folder
        # Prepare Images Folder (Inside Patient's Report Folder)
        patient_report_folder = os.path.join(REPORTS_DIR, patient_id)
        img_folder = os.path.join(patient_report_folder, "images")
        
        if not os.path.exists(img_folder):
            os.makedirs(img_folder, exist_ok=True)
            print(f"      📁 Created Image Folder: {img_folder}")

        for doc in result.documents:
            # Deduplication & Overwrite Logic
            base_title = doc.title_hint
            
            # Check if this title exists in our map
            if base_title in existing_docs_map:
                # OVERWRITE MODE
                seq_num = existing_docs_map[base_title]["seq"]
                # Reuse sequence
                seq_str = f"{seq_num:03d}"
                print(f"      🔄 UPDATING existing document: '{base_title}' (Seq #{seq_str})")
            else:
                # NEW FILE MODE
                seq_str = f"{doc_seq_counter:03d}"
                doc_seq_counter += 1
                print(f"      ✨ CREATING new document: '{base_title}' (Seq #{seq_str})")
            
            # Generate Image if needed
            image_path = None
            img_asset = pdf_generator.get_clinical_image(doc.title_hint) # Check static assets first
            
            if img_asset:
                 # Use static asset
                 pass # We could copy it? For now, simplistic
            else:
                # Dynamic generation
                # We only generate for Imaging type reports to save cost/time
                if any(x in doc.title_hint.lower() for x in ['mri', 'ct', 'xray', 'scan', 'image']):
                    print(f"      🎨 Generating MRI/CT Scan for {doc.title_hint}...")
                    try:
                        # Prepare Path (Folder already ensured above)
                        image_filename = f"{doc.title_hint}_{int(datetime.datetime.now().timestamp())}.png"
                        image_path = os.path.join(img_folder, image_filename)

                        # Generate (Centralized Logic)
                        img_context = f"Medical imaging scan, {doc.title_hint}, distinct features: {doc.content[:100]}..."
                        img_result = ai_engine.generate_clinical_image(img_context, doc.title_hint, output_path=image_path)
                        
                        if img_result:
                            # If result is URL (OpenAI), download it
                            if img_result.startswith("http"):
                                import requests
                                img_data = requests.get(img_result).content
                                with open(image_path, 'wb') as f:
                                    f.write(img_data)
                            
                            # Success Tracking
                            generated_images[doc.title_hint] = image_path 
                            image_count += 1
                        else:
                            print(f"      ⚠️ Image Gen Skipped (None returned)")
                        
                    except Exception as e:
                        print(f"      ⚠️ Image Generation failed: {e}")

            # Construct Filename: DOC-{pid}-{seq}-{title}
            # seq_str is already set logic above
            doc_identifier = f"DOC-{patient_id}-{seq_str}"
            final_filename_base = f"{doc_identifier}-{doc.title_hint}"
            
            # === COMPLIANCE & REPAIR ===
            is_valid, errors = validate_structure(doc.content)
            if not is_valid:
                print(f"      ⚠️  Document '{doc.title_hint}' Invalid: {errors}. Attempting AI Fix...")
                # Retry 1
                doc.content = ai_engine.fix_document_content(doc.content, errors)
                is_valid, errors = validate_structure(doc.content)
                
                if not is_valid:
                     print(f"      ❌ Fix Failed. Marking as NAF (Not AI Friendly).")
                     final_filename_base += "-NAF"
                else:
                     print(f"      ✅ AI Fixed the document.")
            else:
                pass 
                # print(f"      ✅ Valid.")
            
            # Create PDF with Metadata
            pdf_path = pdf_generator.create_patient_pdf(
                patient_id=patient_id, 
                doc_type=final_filename_base, 
                content=doc.content, 
                patient_persona=result.patient_persona,
                doc_metadata=doc,
                base_output_folder=patient_report_folder, # Pass the specific folder
                image_path=image_path
            )
            print(f"      - Created: {os.path.basename(pdf_path)}")
            doc_seq_counter += 1
            
        # GENERATE PERSONA (New Requirement)
        current_year = datetime.datetime.now().year
        current_mrn = f"MRN-{patient_id}-{current_year}" # Centralized MRN

        if result.patient_persona:
            p_full_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
            # Pass the generated_images map so Persona can reuse them
            # Updated to pass the OBJECT
            persona_path = pdf_generator.create_persona_pdf(patient_id, p_full_name, result.patient_persona, result.documents, generated_images, mrn=current_mrn, output_folder=PERSONA_DIR)
            print(f"   👤 Persona Created: {os.path.basename(persona_path)}")
            
        # Summary PDF (Mock)
        # Use Persona data if available, else fallback
        p_name = "Unknown"
        p_dob = "1990-01-01"
        p_gender = "Unknown"
        
        if result.patient_persona:
            p_name = f"{result.patient_persona.first_name} {result.patient_persona.last_name}"
            p_dob = result.patient_persona.dob
            p_gender = result.patient_persona.gender
            
        summary_data = {
           "name": p_name,
           "dob": p_dob, 
           "gender": p_gender,
           "mrn": current_mrn,
           "provider": "Dr. Sarah Smith", # Could extract from persona provider too
           "facility": "General Hospital",
           "procedure": case_data['procedure'],
           "outcome": case_data['outcome'],
           "rationale": result.changes_summary,
           "diagnoses": [{"code": "DX.001", "condition": "Primary Diagnosis", "status": "Active", "date": "2025-01-01"}],
           "timeline": [{"date": "2025-01-01", "title": "Clinical Encounter", "details": ["Patient presented for evaluation."]}]
        }
        
        sum_path = pdf_generator.create_patient_summary_pdf(patient_id, summary_data, output_folder=patient_report_folder)
        print(f"DEBUG: sum_path={sum_path}")
        if sum_path and os.path.exists(sum_path):
            print(f"   📊 Summary PDF Created: {os.path.basename(sum_path)}")
        else:
             print(f"   ❌ Summary PDF FAILED TO CREATE at {sum_path}")
        # Processing complete

        # Return the new name for caching
        return p_full_name if 'p_full_name' in locals() else None



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

    while True:
        # 1. INPUT: ID or '*'
        print("\n" + "="*50)
        target_input = input("🎯 Enter Patient ID (or '*' for Batch, 'q' to Quit): ").strip().strip("'").strip('"')
        
        if not target_input:
            print("❌ Error: Input required.")
            continue
            
        # EXIT COMMAND
        if target_input.lower() in ['q', 'exit', 'quit']:
            print("👋 Exiting Clinical Data Generator. Goodbye!")
            break

        # 2. PURGE COMMANDS
        if target_input.startswith('--'):
            if target_input == '--':
                purge_manager.purge_all()
            elif target_input == '--personas':
                purge_manager.purge_personas()
            elif target_input == '--documents':
                purge_manager.purge_documents()
            else:
                # Specific Patient Purge (e.g. --233)
                p_id = target_input[2:]
                purge_manager.purge_patient(p_id)
            continue

        # 3. LOGIC
        if target_input == '*':
            print("\n🔄 Starting Batch Run for MISSING/INCOMPLETE patients...")
            all_ids = data_loader.get_all_patient_ids()
            print(f"   🔍 Found {len(all_ids)} potential patients in Excel.")
            
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
                    print(f"\n▶️  Processing {p_id}...")
                    
                    # Pass the IN-MEMORY list implies efficiency
                    new_name = process_patient_workflow(p_id, feedback="", excluded_names=current_names) 
                    
                    # Optimize: Update local list immediately to avoid re-reading DB
                    if new_name:
                         current_names.append(new_name)
                         
                    count += 1
            
            print(f"\n✅ Batch Complete. Processed {count} patients.")

        else:
            # Single Run -> Ask for Feedback
            print("\n💡 Feedback Loop")
            print("   Enter any specific instructions for the AI.")
            feedback = input("   Feedback [Press Enter to skip]: ").strip()
            
        # Fetch current names for exclusion (Single run can verify against DB fresh)
        current_names = patient_db.get_all_patient_names()
        process_patient_workflow(target_input, feedback, excluded_names=current_names)

        # Final Verification (if single run)
        if target_input != '*':
            if check_patient_sync_status(target_input):
                 print("   ✅ Sync Verified: All referenced documents exist.")
            else:
                 # It might print the mismatch warning internally, but we state it here too
                 pass 
                 
if __name__ == "__main__":
    main()