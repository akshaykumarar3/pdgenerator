import generator

print("Testing with patient ID '101'...")
name = generator.process_patient_workflow("101")
print(f"Generated for: {name}")

print("Checking sync status...")
status = generator.check_patient_sync_status("101")
print(f"Sync status: {status}")
