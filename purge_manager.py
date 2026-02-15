import os
import shutil
import glob
import json
import core.patient_db as patient_db
from dotenv import load_dotenv

# Load .env (from cred/ directory) - Explicit path since we are in module
env_path = os.path.join(os.path.dirname(__file__), "cred", ".env")
load_dotenv(env_path)

# CONSTANTS
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated_output") # Default

# Derived Paths
DOCS_DIR = os.path.join(OUTPUT_DIR, "patient-reports") # Reports here
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs") # Moved to output dir
SQLS_DIR = os.path.join(OUTPUT_DIR, "sqls")
PERSONAS_DIR = os.path.join(OUTPUT_DIR, "persona") # Singular 'persona' as per plan
SUMMARY_DIR = os.path.join(OUTPUT_DIR, "summary") # Summary PDFs
DB_PATH = patient_db.DB_PATH

def confirm_action(message: str) -> bool:
    """Asks user for confirmation."""
    print(f"\n⚠️  WARNING: {message}")
    response = input("   Are you sure? This cannot be undone. (y/n): ").strip().lower()
    return response == 'y'

def purge_all():
    """
    Clears ALL generated data:
    1. Documents
    2. Summaries
    3. Personas
    4. Logs
    5. SQLs
    6. Patient DB
    """
    if not confirm_action("This will WIPEOUT ALL logs, documents, summaries, personas, SQLs, and the Patient Database."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging ALL Data...")
    
    # 1. Documents
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
        os.makedirs(DOCS_DIR)
        print(f"      ✅ Deleted: {DOCS_DIR}/")

    # 2. Summaries
    if os.path.exists(SUMMARY_DIR):
        shutil.rmtree(SUMMARY_DIR)
        os.makedirs(SUMMARY_DIR)
        print(f"      ✅ Deleted: {SUMMARY_DIR}/")

    # 3. Personas
    if os.path.exists(PERSONAS_DIR):
        shutil.rmtree(PERSONAS_DIR)
        os.makedirs(PERSONAS_DIR)
        print(f"      ✅ Deleted: {PERSONAS_DIR}/")

    # 4. Logs
    if os.path.exists(LOGS_DIR):
        shutil.rmtree(LOGS_DIR)
        os.makedirs(LOGS_DIR)
        print(f"      ✅ Deleted: {LOGS_DIR}/")

    # 5. SQLs
    if os.path.exists(SQLS_DIR):
        files = glob.glob(os.path.join(SQLS_DIR, "*.sql"))
        for f in files:
            os.remove(f)
        print(f"      ✅ Deleted {len(files)} SQL files.")

    # 6. Patient DB
    with open(DB_PATH, 'w') as f:
        json.dump({}, f)
    print(f"      ✅ Reset: {DB_PATH}")

    print("\n   ✨ Purge Complete.")

def purge_personas():
    """
    Clears:
    1. patients_db.json
    2. documents/personas/ folder
    """
    if not confirm_action("This will clear ALL Personas from DB and delete the 'documents/personas' folder."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Personas...")

    # 1. DB
    with open(DB_PATH, 'w') as f:
        json.dump({}, f)
    print(f"      ✅ Reset: {DB_PATH}")

    # 2. Personas Folder
    if os.path.exists(PERSONAS_DIR):
        shutil.rmtree(PERSONAS_DIR)
        print(f"      ✅ Deleted: {PERSONAS_DIR}/")
    
    print("\n   ✨ Personas Purged.")

def purge_documents():
    """
    Clears `documents/` folder content EXCEPT `documents/personas/`.
    """
    if not confirm_action("This will clear ALL Patient Documents (PDFs/Images) but PRESERVE Personas."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Documents (Preserving Personas)...")
    
    if os.path.exists(DOCS_DIR):
        items = os.listdir(DOCS_DIR)
        for item in items:
            item_path = os.path.join(DOCS_DIR, item)
            # Skip personas folder
            if item == "personas":
                continue
            
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        print(f"      ✅ Cleared: {DOCS_DIR}/ (excluding 'personas')")
    
    print("\n   ✨ Documents Purged.")

def purge_summaries_only():
    """
    Deletes ONLY summary PDFs from the summary/ folder.
    """
    if not confirm_action("This will delete ALL Annotator Summary PDFs but preserve Reports and Personas."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Summaries Only...")
    
    count = 0
    # Summaries are in summary/Clinical_Summary_Patient_{id}.pdf
    if os.path.exists(SUMMARY_DIR):
        summary_files = glob.glob(os.path.join(SUMMARY_DIR, "Clinical_Summary_Patient_*.pdf"))
        for f in summary_files:
            os.remove(f)
            count += 1
            print(f"      ✅ Deleted: {os.path.basename(f)}")
    
    print(f"\n   ✨ Deleted {count} summary file(s).")

def purge_reports_only():
    """
    Deletes ONLY report PDFs (DOC-*.pdf) for all patients, preserving summaries and personas.
    """
    if not confirm_action("This will delete ALL Report PDFs but preserve Summaries and Personas."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Reports Only...")
    
    count = 0
    # Reports are DOC-{id}-*.pdf files
    if os.path.exists(DOCS_DIR):
        for patient_folder in os.listdir(DOCS_DIR):
            patient_path = os.path.join(DOCS_DIR, patient_folder)
            if os.path.isdir(patient_path):
                report_files = glob.glob(os.path.join(patient_path, "DOC-*.pdf"))
                for f in report_files:
                    os.remove(f)
                    count += 1
                    print(f"      ✅ Deleted: {os.path.basename(f)}")
                
                # Also delete images folder if it exists
                images_dir = os.path.join(patient_path, "images")
                if os.path.exists(images_dir):
                    shutil.rmtree(images_dir)
                    print(f"      ✅ Deleted: images/ for {patient_folder}")
    
    print(f"\n   ✨ Deleted {count} report file(s).")

def purge_reports_and_summaries():
    """
    Deletes both reports and summaries, but preserves personas.
    """
    if not confirm_action("This will delete ALL Reports and Summaries but preserve Personas."):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Reports and Summaries...")
    
    # Delete patient-reports directory
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
        os.makedirs(DOCS_DIR)
        print(f"      ✅ Deleted: {DOCS_DIR}/")
    
    # Delete summary directory
    if os.path.exists(SUMMARY_DIR):
        shutil.rmtree(SUMMARY_DIR)
        os.makedirs(SUMMARY_DIR)
        print(f"      ✅ Deleted: {SUMMARY_DIR}/")
    
    # Clear logs
    if os.path.exists(LOGS_DIR):
        shutil.rmtree(LOGS_DIR)
        os.makedirs(LOGS_DIR)
        print(f"      ✅ Deleted: {LOGS_DIR}/")
    
    print("\n   ✨ Reports and Summaries Purged.")

def purge_patient(patient_id: str):
    """
    Clears data for a SPECIFIC patient:
    1. Documents/Images (folder)
    2. SQL file
    3. Log entry (file)
    4. DB Entry
    """
    if not confirm_action(f"This will delete ALL data for Patient ID '{patient_id}'."):
        print("   ❌ Operation Cancelled.")
        return

    print(f"\n   🗑️  Purging Patient {patient_id}...")

    # 1. Documents Folder
    p_doc_dir = os.path.join(DOCS_DIR, patient_id)
    if os.path.exists(p_doc_dir):
        shutil.rmtree(p_doc_dir)
        print(f"      ✅ Deleted: {p_doc_dir}/")
    
    # 2. Generated Files in Root Documents? (e.g. DOC-ID-*.pdf if they are not in folder?)
    # Currently generator puts them in `documents/{id}`. 
    # But check for any stray files with ID in name in documents root/
    files = glob.glob(os.path.join(DOCS_DIR, f"*{patient_id}*"))
    for f in files:
        if os.path.isfile(f) and "personas" not in f: # Safety check
            os.remove(f)
            print(f"      ✅ Deleted: {os.path.basename(f)}")

    # 3. SQL File
    # Pattern: *{id}*.sql in sqls/
    sql_files = glob.glob(os.path.join(SQLS_DIR, f"*{patient_id}*.sql"))
    for f in sql_files:
        os.remove(f)
        print(f"      ✅ Deleted: {os.path.basename(f)}")

    # 4. Log File
    log_file = os.path.join(LOGS_DIR, f"{patient_id}.txt")
    if os.path.exists(log_file):
        os.remove(log_file)
        print(f"      ✅ Deleted: {os.path.basename(log_file)}")

    # 5. DB Entry
    with open(DB_PATH, 'r') as f:
        data = json.load(f)
    
    if str(patient_id) in data:
        del data[str(patient_id)]
        with open(DB_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"      ✅ Removed from DB: {patient_id}")
    else:
        print(f"      ℹ️  ID {patient_id} not found in DB.")

    print(f"\n   ✨ Patient {patient_id} Purged.")
