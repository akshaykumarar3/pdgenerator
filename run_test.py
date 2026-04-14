from src.workflow import process_patient_workflow

if __name__ == "__main__":
    process_patient_workflow(
        patient_id="115",
        generation_mode={"persona": False, "reports": False, "summary": True}
    )
