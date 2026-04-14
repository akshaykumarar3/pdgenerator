import os
import shutil
import glob
import json
import datetime
from ..core import patient_db
from ..core.config import (
    OUTPUT_DIR,
    PATIENT_DATA_DIR,
    get_patient_summary_folder,
    get_patient_logs_folder,
    get_patient_records_folder,
    get_patient_archive_folder,
    SUMMARY_DIR,
    DEBUG_DIR,
    get_patient_root,
)
DB_PATH = patient_db.DB_PATH

def confirm_action(message: str, force: bool = False) -> bool:
    """Asks user for confirmation, or skips if force=True."""
    if force: return True
    print(f"\n⚠️  WARNING: {message}")
    response = input("   Are you sure? This cannot be undone. (y/n): ").strip().lower()
    return response == 'y'


def _archive_dir_for_patient(patient_id: str) -> str:
    archive_dir = get_patient_archive_folder(patient_id)
    os.makedirs(archive_dir, exist_ok=True)
    return archive_dir


def _archive_files_for_patient(files: list[str], patient_id: str, label: str):
    archive_dir = _archive_dir_for_patient(patient_id)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{label}_{timestamp}__"
    for f in files:
        if not os.path.isfile(f):
            continue
        dst = os.path.join(archive_dir, f"{prefix}{os.path.basename(f)}")
        shutil.move(f, dst)


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

    p_root = get_patient_root(patient_id)
    p_summary = get_patient_summary_folder(patient_id)

    # Reports
    if "reports" in targets:
        report_files = glob.glob(os.path.join(p_root, f"DOC-{patient_id}-*.pdf"))
        if mode == "archive":
            _archive_files_for_patient(report_files, patient_id, f"{patient_id}_reports")
        else:
            for f in report_files:
                os.remove(f)
                print(f"      ✅ Deleted: {os.path.basename(f)}")

    # Personas
    if "persona" in targets:
        persona_files = glob.glob(os.path.join(p_root, f"{patient_id}-*persona*.pdf"))
        if mode == "archive":
            _archive_files_for_patient(persona_files, patient_id, f"{patient_id}_persona")
        else:
            for f in persona_files:
                os.remove(f)
                print(f"      ✅ Deleted: {os.path.basename(f)}")

    # Summaries
    if "summary" in targets:
        # Search both root (legacy) and dedicated summary folder
        summary_files = glob.glob(os.path.join(p_root, f"Clinical_Summary_Patient_{patient_id}*.pdf"))
        summary_files.extend(glob.glob(os.path.join(p_root, f"Annotator_Summary_Patient_{patient_id}*.pdf")))
        summary_files.extend(glob.glob(os.path.join(p_root, f"Concise_Summary_Patient_{patient_id}*.pdf")))
        if os.path.exists(p_summary):
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Clinical_Summary_Patient_{patient_id}*.pdf")))
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Annotator_Summary_Patient_{patient_id}*.pdf")))
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Concise_Summary_Patient_{patient_id}*.pdf")))
        
        if mode == "archive":
            _archive_files_for_patient(summary_files, patient_id, f"{patient_id}_summary")
        else:
            for f in summary_files:
                try:
                    os.remove(f)
                    print(f"      ✅ Deleted: {os.path.basename(f)}")
                except Exception:
                    pass
                    pass

    # Logs
    if "logs" in targets:
        logs_dir = get_patient_logs_folder(patient_id)
        if os.path.exists(logs_dir):
            if mode == "archive":
                _archive_files_for_patient(
                    glob.glob(os.path.join(logs_dir, "*")),
                    patient_id,
                    f"{patient_id}_logs",
                )
            else:
                shutil.rmtree(logs_dir)
                print(f"      ✅ Deleted: {logs_dir}/")

    # Debug state
    if "debug" in targets:
        debug_state = os.path.join(DEBUG_DIR, f"patient_state_{patient_id}.json")
        if os.path.exists(debug_state):
            if mode == "archive":
                _archive_files_for_patient([debug_state], patient_id, f"{patient_id}_debug")
            else:
                os.remove(debug_state)
                print(f"      ✅ Deleted: {os.path.basename(debug_state)}")

    # Records
    if "records" in targets:
        record_dir = get_patient_records_folder(patient_id)
        record_file = os.path.join(record_dir, f"{patient_id}-record.txt")
        if os.path.exists(record_file):
            if mode == "archive":
                _archive_files_for_patient([record_file], patient_id, f"{patient_id}_records")
            else:
                os.remove(record_file)
                print(f"      ✅ Deleted: {os.path.basename(record_file)}")

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
                archive_dir = _archive_dir_for_patient(patient_id)
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
    
    # 1. Patient Data
    if os.path.exists(PATIENT_DATA_DIR):
        shutil.rmtree(PATIENT_DATA_DIR)
        os.makedirs(PATIENT_DATA_DIR)
        print(f"      ✅ Deleted: {PATIENT_DATA_DIR}/")

    # 5. Patient DB
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"      ✅ Reset: {DB_PATH}")
    except IOError:
        print(f"      ⚠️  Could not reset DB at {DB_PATH}")

    # 2. Additional Folders
    for d in ["logs", "metadata", "archive", "summary"]:
        target_dir = os.path.join(OUTPUT_DIR, d)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            print(f"      ✅ Deleted: {target_dir}/")
    
    if os.path.exists(DEBUG_DIR):
        shutil.rmtree(DEBUG_DIR)
        print(f"      ✅ Deleted: {DEBUG_DIR}/")

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

    # 2. Personas Files
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            for f in glob.glob(os.path.join(p_root, "*-persona-*.pdf")):
                os.remove(f)
                print(f"      ✅ Deleted: {os.path.basename(f)}")
    
    print("\n   ✨ Personas Purged.")

def purge_documents(force: bool = False):
    """
    Clears report + summary folders but preserves personas.
    """
    if not confirm_action("This will clear ALL Patient Documents (PDFs/Images) but PRESERVE Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Documents (Preserving Personas)...")
    
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                for f in glob.glob(os.path.join(p_root, pattern)):
                    os.remove(f)
        
        # Also clear dedicated summary folder
        if os.path.exists(SUMMARY_DIR):
            shutil.rmtree(SUMMARY_DIR)
            os.makedirs(SUMMARY_DIR)
            
        print(f"      ✅ Cleared reports + summaries.")
    
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
    # 1. Clear summary PDFs inside patient folders (legacy)
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                for f in glob.glob(os.path.join(p_root, pattern)):
                    os.remove(f)
                    count += 1
                    print(f"      ✅ Deleted (legacy): {os.path.basename(f)}")
    
    # 2. Clear dedicated summary folder
    if os.path.exists(SUMMARY_DIR):
        shutil.rmtree(SUMMARY_DIR)
        os.makedirs(SUMMARY_DIR)
        print(f"      ✅ Wiped dedicated summary folder: {SUMMARY_DIR}/")
    
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
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            report_files = glob.glob(os.path.join(p_root, "DOC-*.pdf"))
            for f in report_files:
                os.remove(f)
                count += 1
                print(f"      ✅ Deleted: {os.path.basename(f)}")
    
    print(f"\n   ✨ Deleted {count} report file(s).")

def purge_reports_and_summaries(force: bool = False):
    """
    Deletes both reports and summaries, but preserves personas.
    """
    if not confirm_action("This will delete ALL Reports and Summaries but preserve Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Reports and Summaries...")
    
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                for f in glob.glob(os.path.join(p_root, pattern)):
                    os.remove(f)
        
        # Also clear dedicated summary folder
        if os.path.exists(SUMMARY_DIR):
            shutil.rmtree(SUMMARY_DIR)
            os.makedirs(SUMMARY_DIR)
            
        print(f"      ✅ Deleted: reports + summaries.")
    
    print("\n   ✨ Reports and Summaries Purged.")

def purge_patient(patient_id: str, force: bool = False):
    """
    Clears data for a SPECIFIC patient:
    Default: persona, reports, summary, logs, db, records, debug
    """
    default_targets = ["persona", "reports", "summary", "logs", "db", "records", "debug"]
    purge_patient_selective(patient_id, default_targets, mode="delete", force=force)
