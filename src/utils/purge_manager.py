import os
import shutil
import glob
import json
import datetime
from ..core import patient_db
from ..core.config import OUTPUT_DIR, REPORTS_DIR, SUMMARY_DIR, LOGS_DIR, RECORDS_DIR, PERSONA_DIR

# Derived Paths (Mapped from config)
DOCS_DIR = REPORTS_DIR
PERSONAS_DIR = PERSONA_DIR
DB_PATH = patient_db.DB_PATH

def confirm_action(message: str, force: bool = False) -> bool:
    """Asks user for confirmation, or skips if force=True."""
    if force: return True
    print(f"\n⚠️  WARNING: {message}")
    response = input("   Are you sure? This cannot be undone. (y/n): ").strip().lower()
    return response == 'y'


def _archive_dir(base_dir: str) -> str:
    archive_dir = os.path.join(base_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    return archive_dir


def _archive_files(files: list[str], base_dir: str):
    archive_dir = _archive_dir(base_dir)
    for f in files:
        if not os.path.isfile(f):
            continue
        dst = os.path.join(archive_dir, os.path.basename(f))
        shutil.move(f, dst)


def _archive_folder(folder_path: str, base_dir: str, label: str):
    if not os.path.exists(folder_path):
        return
    archive_dir = _archive_dir(base_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(archive_dir, f"{label}_{timestamp}")
    shutil.move(folder_path, dst)


def purge_patient_selective(patient_id: str, targets: list[str], mode: str = "delete", force: bool = False):
    """
    Clears data for a SPECIFIC patient based on targets.
    targets: persona, reports, summary, logs, db, records, debug
    mode: delete | archive
    """
    if mode not in {"delete", "archive"}:
        raise ValueError("Invalid purge mode. Use 'delete' or 'archive'.")
    if not targets:
        return
    targets = [t.lower() for t in targets]

    msg = f"This will {mode} data for Patient ID '{patient_id}' -> {', '.join(targets)}."
    if not confirm_action(msg, force=force):
        print("   ❌ Operation Cancelled.")
        return

    print(f"\n   🗑️  Purging Patient {patient_id} ({mode})...")

    # Reports (patient-reports/<id>/)
    if "reports" in targets:
        p_doc_dir = os.path.join(DOCS_DIR, str(patient_id))
        if mode == "archive":
            _archive_folder(p_doc_dir, DOCS_DIR, f"{patient_id}_reports")
        else:
            if os.path.exists(p_doc_dir):
                shutil.rmtree(p_doc_dir)
                print(f"      ✅ Deleted: {p_doc_dir}/")

    # Personas
    if "persona" in targets:
        persona_files = glob.glob(os.path.join(PERSONAS_DIR, f"*{patient_id}*"))
        if mode == "archive":
            _archive_files(persona_files, PERSONAS_DIR)
        else:
            for f in persona_files:
                if os.path.isfile(f):
                    os.remove(f)
                    print(f"      ✅ Deleted: personas/{os.path.basename(f)}")

    # Summaries
    if "summary" in targets:
        summary_files = glob.glob(os.path.join(SUMMARY_DIR, f"*{patient_id}*"))
        if mode == "archive":
            _archive_files(summary_files, SUMMARY_DIR)
        else:
            for f in summary_files:
                if os.path.isfile(f):
                    os.remove(f)
                    print(f"      ✅ Deleted: summary/{os.path.basename(f)}")

    # Logs
    if "logs" in targets:
        log_file = os.path.join(LOGS_DIR, f"{patient_id}.txt")
        if os.path.exists(log_file):
            if mode == "archive":
                _archive_files([log_file], LOGS_DIR)
            else:
                os.remove(log_file)
                print(f"      ✅ Deleted: {os.path.basename(log_file)}")

    # Debug state
    if "debug" in targets:
        debug_state = os.path.join(OUTPUT_DIR, "debug", f"patient_state_{patient_id}.json")
        if os.path.exists(debug_state):
            if mode == "archive":
                _archive_files([debug_state], os.path.join(OUTPUT_DIR, "debug"))
            else:
                os.remove(debug_state)
                print(f"      ✅ Deleted: {os.path.basename(debug_state)}")

    # Records
    if "records" in targets:
        if os.path.exists(RECORDS_DIR):
            record_files = glob.glob(os.path.join(RECORDS_DIR, f"*{patient_id}*"))
            if mode == "archive":
                _archive_files(record_files, RECORDS_DIR)
            else:
                for f in record_files:
                    if os.path.isfile(f):
                        os.remove(f)
                        print(f"      ✅ Deleted: records/{os.path.basename(f)}")

    # DB entry
    if "db" in targets:
        data = {}
        if os.path.exists(DB_PATH):
            try:
                with open(DB_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                data = {}
        if str(patient_id) in data:
            if mode == "archive":
                archive_dir = _archive_dir(RECORDS_DIR)
                archive_path = os.path.join(archive_dir, f"patient_{patient_id}_db.json")
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump(data[str(patient_id)], f, indent=2)
                print(f"      ✅ Archived DB entry: {os.path.basename(archive_path)}")
            del data[str(patient_id)]
            with open(DB_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"      ✅ Removed from DB: {patient_id}")
        else:
            print(f"      ℹ️  ID {patient_id} not found in DB.")

    print(f"\n   ✨ Patient {patient_id} Purge Complete.")

def purge_all(force: bool = False):
    """
    Clears ALL generated data:
    1. Documents
    2. Summaries
    3. Personas
    4. Logs
    5. Patient DB
    6. Records
    """
    if not confirm_action("This will WIPEOUT ALL logs, documents, summaries, personas, records, and the Patient Database.", force=force):
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

    # 5. Patient DB
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"      ✅ Reset: {DB_PATH}")
    except IOError:
        print(f"      ⚠️  Could not reset DB at {DB_PATH}")

    # 6. Records
    if os.path.exists(RECORDS_DIR):
        shutil.rmtree(RECORDS_DIR)
        os.makedirs(RECORDS_DIR)
        print(f"      ✅ Deleted: {RECORDS_DIR}/")

    print("\n   ✨ Purge Complete.")

def purge_personas(force: bool = False):
    """
    Clears:
    1. patients_db.json
    2. documents/personas/ folder
    """
    if not confirm_action("This will clear ALL Personas from DB and delete the 'documents/personas' folder.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Personas...")

    # 1. DB
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"      ✅ Reset: {DB_PATH}")
    except IOError:
        print(f"      ⚠️  Could not reset DB at {DB_PATH}")

    # 2. Personas Folder
    if os.path.exists(PERSONAS_DIR):
        shutil.rmtree(PERSONAS_DIR)
        print(f"      ✅ Deleted: {PERSONAS_DIR}/")
    
    print("\n   ✨ Personas Purged.")

def purge_documents(force: bool = False):
    """
    Clears `documents/` folder content EXCEPT `documents/personas/`.
    """
    if not confirm_action("This will clear ALL Patient Documents (PDFs/Images) but PRESERVE Personas.", force=force):
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

def purge_summaries_only(force: bool = False):
    """
    Deletes ONLY summary PDFs from the summary/ folder.
    """
    if not confirm_action("This will delete ALL Annotator Summary PDFs but preserve Reports and Personas.", force=force):
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

def purge_reports_only(force: bool = False):
    """
    Deletes ONLY report PDFs (DOC-*.pdf) for all patients, preserving summaries and personas.
    """
    if not confirm_action("This will delete ALL Report PDFs but preserve Summaries and Personas.", force=force):
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

def purge_reports_and_summaries(force: bool = False):
    """
    Deletes both reports and summaries, but preserves personas.
    """
    if not confirm_action("This will delete ALL Reports and Summaries but preserve Personas.", force=force):
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

def purge_patient(patient_id: str, force: bool = False):
    """
    Clears data for a SPECIFIC patient:
    Default: persona, reports, summary, logs, db, records, debug
    """
    default_targets = ["persona", "reports", "summary", "logs", "db", "records", "debug"]
    purge_patient_selective(patient_id, default_targets, mode="delete", force=force)
