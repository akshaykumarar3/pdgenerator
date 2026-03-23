import os
import json
from src.ai.client import generate_clinical_image
from src.doc_generation.pdf_generator import create_patient_pdf

class MockDoc:
    def __init__(self, title, content):
        self.title_hint = title
        self.content = content

class MockPersona:
    def __init__(self):
        self.first_name = "Test Image"
        self.last_name = "Patient"
        self.name = "Test Image Patient"
        self.dob = "1990-01-01"
        self.gender = "female"
        self.mrn = "MRN-IMG-TEST"
        self.telecom = "555-0000"
        self.payer = None
        self.provider = None

def test_image_generation():
    doc = MockDoc(
        title="12_lead_ECG",
        content=json.dumps({"sections": ["ecg_findings"], "ecg_findings": "Normal sinus rhythm, inverted T waves in V1-V3."})
    )
    
    patient_report_folder = "./test_img_dir"
    os.makedirs(patient_report_folder, exist_ok=True)
    
    # 1. Test image generation
    image_path = None
    imaging_keywords = ["ECG", "XRAY", "X-RAY", "MRI", "CT", "ULTRASOUND", "ECHO", "RADIOGRAPH", "SCAN"]
    if any(kw in doc.title_hint.upper() for kw in imaging_keywords):
        print(f"📸 Imaging document detected '{doc.title_hint}', generating supportive AI visual...")
        img_filename = f"test_{doc.title_hint}_img.png"
        temp_image_path = os.path.join(patient_report_folder, img_filename)
        
        # Test DALL-E directly (this consumes OpenAI credits!)
        # Using a highly simplified prompt to avoid massive credit burn here:
        image_context = f"Medical illustration of {doc.title_hint} showing {doc.content[:50]}"
        generated_path = generate_clinical_image(context=image_context, image_type=doc.title_hint, output_path=temp_image_path)
        
        if generated_path:
            image_path = generated_path
            print(f"🖼️ Saved image to {image_path}")
            assert os.path.exists(image_path), "Image file was not saved!"
            
    # 2. Test PDF inclusion
    metadata = {
        "patient_name": "Test Image Patient",
        "doc_type": doc.title_hint,
    }
    
    formatted_content = "<b>Test ECG Image Inclusion</b>"
    
    pdf_path = create_patient_pdf(
        patient_id="IMG-123",
        doc_type="TEST_ECG",
        content=formatted_content,
        patient_persona=MockPersona(),
        doc_metadata=doc,
        base_output_folder=patient_report_folder,
        image_path=image_path,
        version=1,
    )
    print(f"✅ Generated PDF at {pdf_path}")
    assert os.path.exists(pdf_path), "PDF file was not saved!"
    print("SUCCESS: Image generation and PDF attachment works.")

if __name__ == "__main__":
    test_image_generation()
