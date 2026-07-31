
import unittest
import os
import json
from src.ai.prompts import get_clinical_data_prompt

class TestTemplateSelection(unittest.TestCase):

    def setUp(self):
        self.case_details = {
            'procedure': 'Test Procedure',
            'outcome': 'Test Outcome',
            'details': 'Test Details'
        }
        self.patient_state = {}
        with open("templates/persona_template.json", "r") as f:
            self.document_plan = json.load(f)

    def test_default_template(self):
        prompt = get_clinical_data_prompt(
            self.case_details,
            self.patient_state,
            self.document_plan
        )
        self.assertIn('"title": "Patient Persona Record"', prompt)

    def test_kca_template_is_loaded(self):
        prompt = get_clinical_data_prompt(
            self.case_details,
            self.patient_state,
            self.document_plan,
            user_feedback=
            'use KCA template'
        )
        self.assertIn('"title": "KCA Patient Persona Record"', prompt)

    def test_default_template_is_loaded_when_no_template_in_feedback(self):
        prompt = get_clinical_data_prompt(
            self.case_details,
            self.patient_state,
            self.document_plan,
            user_feedback=
            'some other feedback'
        )
        self.assertIn('"title": "Patient Persona Record"', prompt)

    def test_kca_template(self):
        prompt = get_clinical_data_prompt(
            self.case_details,
            self.patient_state,
            self.document_plan,
            user_feedback='use KCA template'
        )
        self.assertIn('"title": "KCA Patient Persona Record"', prompt)

if __name__ == '__main__':
    unittest.main()
