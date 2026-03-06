import generator

pid = "210"
print(f"--- Initial status for {pid} ---")
print("Sync status:", generator.check_patient_sync_status(pid))

print(f"\n--- Purging {pid} ---")
import purge_manager
purge_manager.purge_patient(pid)

print(f"\n--- After purge status for {pid} ---")
print("Sync status:", generator.check_patient_sync_status(pid))

print(f"\n--- Generating for {pid} (1st run) ---")
generator.process_patient_workflow(pid, generation_mode={"persona": True, "reports": True, "summary": True})
import os
print("\nPersona dir:", os.listdir(generator.PERSONA_DIR))

print(f"\n--- Generating for {pid} (2nd run to test archive) ---")
generator.process_patient_workflow(pid, generation_mode={"persona": True, "reports": True, "summary": True})
print("\nPersona archive dir:", os.listdir(os.path.join(generator.PERSONA_DIR, "archive")))

