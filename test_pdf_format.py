import json
from pdf_generator import format_report_content

def test_recursive_formatting():
    # Simulate a deeply nested payload similar to "Encounters Documentation"
    payload = {
        "sections": ["encounters"],
        "encounters": [
            {
                "encounter_date": "2026-01-05",
                "encounter_type": "Office Visit",
                "purpose_of_visit": "Initial presentation of chest pain.",
                "diagnoses": [{"code": "I25.10", "description": "Atherosclerotic heart disease"}],
                "vital_signs": {
                    "recorded_date": "2026-01-05",
                    "blood_pressure": "135/85 mmHg"
                },
                "procedures_performed": ["99213", "93000"]
            }
        ]
    }
    
    # Test formatting
    formatted_html = format_report_content(payload)
    
    print("Formatted HTML Output:\n" + "="*40)
    print(formatted_html)
    print("="*40)
    
    # Assertions
    assert "{'code':" not in formatted_html, "Raw dictionary string detected!"
    assert "<b>Atherosclerotic Heart Disease</b>" in formatted_html or "Atherosclerotic heart disease" in formatted_html, "Nested dictionary value missing!"
    print("SUCCESS: JSON was recursively parsed into HTML")

if __name__ == "__main__":
    test_recursive_formatting()
