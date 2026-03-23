import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import workflow

print("\n--- Generating for 211 (Testing Summary fix) ---")
workflow.process_patient_workflow("211", generation_mode={"persona": True, "reports": True, "summary": True})

from src.core.config import SUMMARY_DIR
print("Summary Dir:", os.listdir(SUMMARY_DIR))
