import generator
print("\n--- Generating for 211 (Testing Summary fix) ---")
generator.process_patient_workflow("211", generation_mode={"persona": True, "reports": True, "summary": True})
import os
from core.config import SUMMARY_DIR
print("Summary Dir:", os.listdir(SUMMARY_DIR))
