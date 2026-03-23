import sys
import argparse
from purge_manager import purge_patient

def main():
    parser = argparse.ArgumentParser(description="Completely remove all data and history for a specific persona.")
    parser.add_argument("patient_id", nargs="?", help="The ID of the patient/persona to remove.")
    parser.add_argument("--force", "-f", action="store_true", help="Force removal without asking for confirmation.")
    
    args = parser.parse_args()
    
    patient_id = args.patient_id
    if not patient_id:
        patient_id = input("Enter Patient ID to remove: ").strip()
        
    if not patient_id:
        print("Error: Patient ID is required.")
        sys.exit(1)
        
    print(f"Starting removal process for patient '{patient_id}'...")
    purge_patient(patient_id, force=args.force)
    print("Removal process complete.")

if __name__ == "__main__":
    main()
