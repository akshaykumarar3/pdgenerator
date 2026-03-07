import asyncio
import json
from ai_engine import generate_clinical_data

def test_feedback():
    case_details = {
        "procedure": "CPT 78452 - Myocardial perfusion imaging, tomographic (SPECT) (including attenuation correction, qualitative or quantitative wall motion, ejection fraction by first pass or gated technique, additional quantification, when performed); multiple studies, at rest and/or stress (exercise or pharmacologic) and/or re-injection",
        "outcome": "Approval",
        "details": "Patient presents with persistent chest pain and needs an MPI."
    }
    
    patient_state = {
        "identifiers": {"mrn": "MRN-123456"}
    }
    
    document_plan = {
        "clinical_note": {
            "title": "Clinical Note",
            "narrative": "Patient note."
        }
    }
    
    feedback = '''Below is the list of missing information, Add the following and recreate 
- Missing recent ECG
- Missing detailed chest pain symptom characteristics
- Missing basic physical examination findings
- Missing documentation of preliminary cardiac diagnostic steps
- Absence of payer policy documents, preventing assessment against specific coverage criteria.
- Absence of all supporting clinical documentation (e.g., medical records, lab results, imaging reports), which are critical for demonstrating medical necessity and policy alignment.
- Absence of clinical timeline
- Lack of supporting medical documentation (e.g., patient notes, lab results, imaging reports)
- Missing or empty administrative fields (e.g., patient phone number, provider address, plan type)
- Incomplete patient demographic details at the top-level request.
No clinical timeline data provided'''

    print("Generating clinical data...")
    try:
        response_tuple = generate_clinical_data(
            case_details=case_details,
            patient_state=patient_state,
            document_plan=document_plan,
            user_feedback=feedback
        )
        # handle depending on whether it returns a single item or a tuple
        payload = response_tuple[0] if isinstance(response_tuple, tuple) else response_tuple
        
        print("\n--- PATIENT PERSONA ---")
        print(f"Phone: {payload.patient_persona.telecom}")
        print(f"Provider Address: {payload.patient_persona.provider.address}")
        print(f"Provider Phone: {payload.patient_persona.provider.phone}")
        print(f"Plan Type: {payload.patient_persona.payer.plan_type}")
        print(f"Demographics Check - DOB: {payload.patient_persona.dob}, Gender: {payload.patient_persona.gender}")
        
        print(f"\nEncounters count: {len(payload.patient_persona.encounters)}")
        print(f"Vital Signs collected: {bool(payload.patient_persona.vital_signs_current)}")
        
        print("\n--- DOCUMENTS GENERATED ---")
        for idx, doc in enumerate(payload.documents):
            print(f"Document {idx+1}: {doc.title_hint}")
            doc_content = json.loads(doc.content)
            # Find if it looks like an ECG, Payer Policy, etc.
            keys = list(doc_content.keys())[:3]
            print(f"  Keys: {keys}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_feedback()
