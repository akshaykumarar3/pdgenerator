import os
import sys

# Setup paths like run.py
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))

# Mock OUTPUT_DIR before importing config
import os
os.environ["OUTPUT_DIR"] = os.path.join(project_root, "test_generated_output")

from core.config import get_patient_summary_folder, SUMMARY_DIR, ensure_output_dirs

def test():
    ensure_output_dirs()
    p_id = "225"
    summary_folder = get_patient_summary_folder(p_id)
    print(f"Summary folder for patient {p_id}: {summary_folder}")
    print(f"Goal SUMMARY_DIR: {SUMMARY_DIR}")
    
    # Verification: summary folder is now flat (returns SUMMARY_DIR directly)
    if summary_folder == SUMMARY_DIR:
        print("✅ Path verification passed: summary folder is flat.")
    else:
        print(f"❌ Path verification failed: summary folder is NOT flat. Got {summary_folder}")
        sys.exit(1)
    
    # Check if a dummy file can be written and found by purge logic
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)
        
    dummy_file = os.path.join(SUMMARY_DIR, f"Clinical_Summary_Patient_{p_id}_v99.pdf")
    with open(dummy_file, "w") as f:
        f.write("dummy content")
    print(f"Created dummy summary: {dummy_file}")
    
    from utils.purge_manager import purge_patient_selective
    # Mock confirm_action to return True
    import utils.purge_manager
    utils.purge_manager.confirm_action = lambda msg, force=False: True
    
    print("Running purge_patient_selective for 'summary'...")
    purge_patient_selective(p_id, ["summary"], force=True)
    
    if not os.path.exists(dummy_file):
        print("✅ Purge verification passed: dummy summary deleted from flat folder.")
    else:
        print("❌ Purge verification failed: dummy summary still exists.")
        sys.exit(1)
    
    # Cleanup test output
    import shutil
    shutil.rmtree(os.environ["OUTPUT_DIR"])
    print("✅ Cleanup complete.")

if __name__ == "__main__":
    test()
