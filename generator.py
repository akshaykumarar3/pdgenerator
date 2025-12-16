import os


import data_loader
import ai_engine
import pdf_generator
import history_manager
import requests
import datetime
import core.patient_db as patient_db
import purge_manager

def main():
    print("\n🚀 Clinical Data Generator (v2.0) - Modular & Interactive")
def process_patient_workflow(patient_id: str, feedback: str = "", excluded_names: list[str] = None):
    """
    Main orchestration logic for a single patient.
    """
    if excluded_names is None:
        excluded_names = []
    # --- CONDITIONAL SQL LOGIC ---
    # Syntax: "237" -> No SQL, "237-sql" -> Generate SQL
    generate_sql = False
    input_patient_id = patient_id # Store original patient_id for checking suffix
    if input_patient_id.endswith("-sql"):
        generate_sql = True
        patient_id = input_patient_id[:-4] # Remove "-sql"
    else:
        patient_id = input_patient_id
        
    print(f"🚀 Starting Workflow for Patient ID: {patient_id} (SQL Generation: {generate_sql})")

    print(f"\n📂 Loading Case Data for ID: {patient_id}...")
    case_data = data_loader.load_patient_case(patient_id)
    
    if not case_data:
        print(f"❌ Error: Patient ID '{patient_id}' not found in Excel Plan.")
        return

    print(f"   ✅ Case Found: {case_data['procedure']} -> {case_data['outcome']}")

    source_sql_path = data_loader.find_sql_file(patient_id)
    if not source_sql_path:
        # Fallback: Use a template if specific file missing
        source_sql_path = data_loader.get_template_sql()
        if source_sql_path:
             print(f"   ⚠️  Notice: Source SQL missing. Using template: {os.path.basename(source_sql_path)}")
        else:
             print(f"❌ Error: No SQL file found for Patient {patient_id} and no template available.")
             return
    
    with open(source_sql_path, 'r') as f:
        original_sql = f.read()
    
    # LOAD HISTORY
    history_txt = history_manager.get_history(patient_id)
    if history_txt:
        print(f"   📜 History Found: Loaded past context.")

    # 4. Check Persistent DB for Consistency
    existing_patient = patient_db.load_patient(patient_id)
    persona_context_prompt = ""
    if existing_patient:
        print(f"      🔄 Found Existing Patient Record: {existing_patient.get('first_name')} {existing_patient.get('last_name')}")
        persona_context_prompt = f"""
        **IMMUTABLE PATIENT IDENTITY (FROM DATABASE):**
        - Name: {existing_patient.get('first_name')} {existing_patient.get('last_name')}
        - Gender: {existing_patient.get('gender', 'Unknown')}
        - DOB: {existing_patient.get('dob', 'Unknown')}
        - Address: {existing_patient.get('address', 'Unknown')}
        - CORE PERSONA: {existing_patient.get('bio_narrative', 'N/A')[:200]}...
        - **DO NOT CHANGE THESE DETAILS.**
        """

    # ... process ...
    print(f"🧠 Processing with AI... (Outcome: {case_data['outcome']})")
    schema = data_loader.get_db_schema()

    try:
        # Pass existing history + persona context
        full_history = history_txt + "\n" + persona_context_prompt
        
        result, usage = ai_engine.modify_sql(original_sql, schema, case_data, feedback, full_history, existing_persona=existing_patient, excluded_names=excluded_names)
        
        # SAVE HISTORY
        history_manager.append_history(patient_id, feedback, result.changes_summary)
        
        # Output SQL
        # Output SQL (Conditional)
        if generate_sql:
            out_path = data_loader.save_sql(patient_id, result.updated_sql)
            print(f"   ✅ SQL Saved: {os.path.basename(out_path)}")
        else:
            print(f"   🚫 SQL Generation Skipped (Mode: No-SQL)")
        
        # GENERATE PDFs (Dynamic + Unique)
        print(f"   📄 Generating {len(result.documents)} Document(s)...")
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

        # 7. Generate Documents
        generated_images = {} # Map title -> file_path
        image_count = 0
        
        # Prepare Images Folder
        img_folder = os.path.abspath(f"documents/{patient_id}/images")
        if not os.path.exists(img_folder):
            os.makedirs(img_folder, exist_ok=True)
            print(f"      📁 Created Image Folder: {img_folder}")

        doc_seq_counter = 1
        for doc in result.documents:
            # Deduplication
            base_title = doc.title_hint
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
            seq_str = f"{doc_seq_counter:03d}"
            doc_identifier = f"DOC-{patient_id}-{seq_str}"
            final_filename_base = f"{doc_identifier}-{doc.title_hint}"
            
            # Create PDF with Metadata
            pdf_path = pdf_generator.create_patient_pdf(
                patient_id=patient_id, 
                doc_type=final_filename_base, 
                content=doc.content, 
                patient_persona=result.patient_persona,
                doc_metadata=doc,
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
            persona_path = pdf_generator.create_persona_pdf(patient_id, p_full_name, result.patient_persona, result.documents, generated_images, mrn=current_mrn)
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
        
        sum_path = pdf_generator.create_patient_summary_pdf(patient_id, summary_data)
        print(f"DEBUG: sum_path={sum_path}")
        if sum_path and os.path.exists(sum_path):
            print(f"   📊 Summary PDF Created: {os.path.basename(sum_path)}")
        else:
             print(f"   ❌ Summary PDF FAILED TO CREATE at {sum_path}")
        # Processing complete

    except Exception as e:
        print(f"❌ Error during processing: {e}")


def check_patient_sync_status(patient_id: str) -> bool:
    """
    Verification Logic:
    1. SQL Mode: If _final.sql exists, PDF count must match SQL INSERTs.
    2. No-SQL Mode: If _final.sql missing, at least one PDF must exist.
    """
    sql_path = f"sqls/{patient_id}_final.sql"
    doc_folder = f"documents/{patient_id}"

    # Smart Migration: Rename old summary if needed
    old_summary = os.path.join(doc_folder, f"Patient_{patient_id}_Clinical_Summary.pdf")
    new_summary = os.path.join(doc_folder, f"Clinical_Summary_Patient_{patient_id}.pdf")
    
    if os.path.exists(old_summary) and not os.path.exists(new_summary):
        try:
            os.rename(old_summary, new_summary)
            print(f"   ✨ Migrated Summary for {patient_id}")
        except Exception as e:
            print(f"   ⚠️ Failed to migrate summary for {patient_id}: {e}")

    # Check for Documents
    if not os.path.exists(doc_folder):
        return False
        
    pdf_files = [f for f in os.listdir(doc_folder) if f.lower().endswith('.pdf')]
    # Exclude summary from count
    actual_count = len([f for f in pdf_files if "clinical_summary" not in f.lower()])

    if not os.path.exists(sql_path):
        # No-SQL Mode: Valid if we have generated documents
        if actual_count > 0:
            return True
        else:
            print(f"   ⚠️  No SQL and No Documents found for {patient_id}")
            return False
        
    try:
        # SQL Mode: Count Expected Docs from SQL
        with open(sql_path, 'r') as f:
            sql_content = f.read()
            
            # Robust Heuristic: Count INSERT statements for documents
            # Case insensitive count of "INSERT INTO mockdata.document_reference_fhir"
            expected_count = sql_content.lower().count("insert into mockdata.document_reference_fhir")

        if expected_count > 0:
            is_valid = actual_count >= expected_count
            if not is_valid:
                 print(f"   ⚠️  Sync Mismatch: SQL expects {expected_count} documents, but found {actual_count}.")
            return is_valid
        else:
            return True # SQL exists but no docs inserted?
            
    except Exception as e:
        print(f"Error checking sync for {patient_id}: {e}")
        return False

def main():
    print("\n🚀 Clinical Data Generator (v2.0) - Modular & Interactive")
    
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
            
            count = 0
            for p_id in all_ids:
                # Smart Skip Logic
                if check_patient_sync_status(p_id):
                    print(f"   ⏭️  Skipping {p_id} (Verified Complete)")
                else:
                    print(f"\n▶️  Processing {p_id}...")
                    # Fetch used names for this batch run
                    current_names = patient_db.get_all_patient_names()
                    process_patient_workflow(p_id, feedback="", excluded_names=current_names) 
                    count += 1
            
            print(f"\n✅ Batch Complete. Processed {count} patients.")

        else:
            # Single Run -> Ask for Feedback
            print("\n💡 Feedback Loop")
            print("   Enter any specific instructions for the AI.")
            feedback = input("   Feedback [Press Enter to skip]: ").strip()
            
            # Single Run -> Ask for Feedback
        print("\n💡 Feedback Loop")
        print("   Enter any specific instructions for the AI.")
        feedback = input("   Feedback [Press Enter to skip]: ").strip()
        
        # Fetch current names for exclusion
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