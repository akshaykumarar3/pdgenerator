"""
Unit tests for prior authorization pipeline enhancements.
"""
import os
import sys
import unittest

# Ensure src is importable
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_BASE_DIR, "src"))
sys.path.insert(0, _BASE_DIR)

from src.core.config import MAX_SUPPORTING_DOCUMENTS
from src.doc_generation.planner import detect_case_type, select_document_plan, RULES_PATH
from src.doc_generation.patient_tracker_export import generate_tracker_export

from src.core import patient_db

import tempfile
import shutil
import src.core.config as config
import src.doc_generation.patient_tracker_export as tracker_export

class TestPriorAuthTracker(unittest.TestCase):
    def setUp(self):
        os.environ["PATIENT_STORAGE_BACKEND"] = "json"
        patient_db._repository = None
        self.test_dir = tempfile.mkdtemp()
        self.orig_output_dir = config.OUTPUT_DIR
        self.orig_patient_data_dir = config.PATIENT_DATA_DIR
        self.orig_export_data_dir = tracker_export.PATIENT_DATA_DIR
        config.OUTPUT_DIR = self.test_dir
        config.PATIENT_DATA_DIR = os.path.join(self.test_dir, "patient-data")
        tracker_export.PATIENT_DATA_DIR = config.PATIENT_DATA_DIR

    def tearDown(self):
        config.OUTPUT_DIR = self.orig_output_dir
        config.PATIENT_DATA_DIR = self.orig_patient_data_dir
        tracker_export.PATIENT_DATA_DIR = self.orig_export_data_dir
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rules_path_resolution(self):
        """Verify planner correctly resolves the rules path in templates/."""
        self.assertTrue(os.path.exists(RULES_PATH), f"Rules path does not exist: {RULES_PATH}")
        self.assertTrue(RULES_PATH.endswith(os.path.join("templates", "document_plan_rules.json")))

    def test_hcpcs_case_type_detection(self):
        """Verify J/Q codes are detected as 'medication'."""
        self.assertEqual(detect_case_type("Therapy infusion", "J0897"), "medication")
        self.assertEqual(detect_case_type("Injection", "Q5124"), "medication")
        self.assertEqual(detect_case_type("J0897 Infusion"), "medication")
        self.assertEqual(detect_case_type("Q5124 Drug therapy"), "medication")
        
        # Verify non-medication codes default correctly
        self.assertEqual(detect_case_type("Cardiac CT Angiography", "75574"), "imaging")
        self.assertEqual(detect_case_type("Routine Consult", "99203"), "diagnostic")

    def test_document_capping(self):
        """Verify that select_document_plan caps supporting documents to MAX_SUPPORTING_DOCUMENTS."""
        self.assertEqual(MAX_SUPPORTING_DOCUMENTS, 5)
        
        # Test imaging (originally has 5 reports)
        plan_imaging = select_document_plan("imaging")
        supporting_imaging = [t for t in plan_imaging if t != "prior_auth_request_template.json" and "summary" not in t]
        self.assertLessEqual(len(supporting_imaging), 5)
        
        # Test medication (originally has 5 reports)
        plan_med = select_document_plan("medication")
        supporting_med = [t for t in plan_med if t != "prior_auth_request_template.json" and "summary" not in t]
        self.assertLessEqual(len(supporting_med), 5)

    def test_tracker_export_runs(self):
        """Verify that generate_tracker_export can execute without errors and generates files with 12 columns."""
        import csv
        # We can pass a dummy patient ID that does not exist to verify the fallback compilation logic
        csv_path = generate_tracker_export(["99999"])
        self.assertTrue(os.path.exists(csv_path))
        self.assertTrue(csv_path.endswith(".csv"))
        
        # Verify the CSV columns match our 12-column schema exactly
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=",")
                rows = list(reader)
                
                columns = rows[0]
                expected_columns = [
                    "Patient ID", "Patient Name", "Department", "CPT/HCPC Code",
                    "Procedure/Medicine Name", "Provider", "Insurance Type", "Policy Name",
                    "extraction expectation", "likelihood expectations", "attachments",
                    "post-attachment likelihood"
                ]
                
                self.assertEqual(len(columns), 12)
                self.assertEqual(columns, expected_columns)
                
                # Check data row format
                self.assertGreater(len(rows), 1)
                data_fields = rows[1]
                self.assertEqual(len(data_fields), 12)
                self.assertEqual(data_fields[0], "99999") # Patient ID
        except Exception as e:
            self.fail(f"CSV schema verification failed: {e}")
        finally:
            # Clean up generated test outputs
            try:
                os.remove(csv_path)
            except Exception:
                pass

    def test_tracker_fallback_rich_fields(self):
        """Verify that fallback data fields are rich and contain no raw HTML tags in the CSV."""
        import csv
        csv_path = generate_tracker_export(["99999"])
        
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=",")
                rows = list(reader)
                
            self.assertGreater(len(rows), 1)
            data_row = rows[1]
            
            # Verify columns do not contain HTML tags
            for cell in data_row:
                self.assertNotIn("<b>", cell)
                self.assertNotIn("</b>", cell)
                self.assertNotIn("<br/>", cell)
                self.assertNotIn("<font", cell)
                self.assertNotIn("</font>", cell)
                
            # Verify clinical expectations and details are richly populated
            extraction = data_row[8]  # extraction expectation
            likelihood = data_row[9]  # likelihood expectations
            post_likelihood = data_row[11] # post-attachment likelihood
            
            # Since patient 99999 is a dummy, it uses the fallback path
            self.assertIn("Expected Service:", extraction)
            self.assertIn("Required Criteria:", extraction)
            self.assertIn("likelihood of approval", likelihood.lower())
            self.assertIn("Likelihood", post_likelihood)
            
        finally:
            # Clean up generated test outputs
            try:
                os.remove(csv_path)
            except Exception:
                pass

    def test_hcpcs_labeling_in_tracker(self):
        """Verify that medication cases with HCPCS/HCPC codes are dynamically labeled as HCPC instead of CPT."""
        import csv
        from unittest.mock import patch
        
        mock_case = {
            "test_case_num": "88888",
            "department": "medication",
            "cpt_code": "J0897",
            "procedure": "J0897 Infusion",
            "outcome": "approval",
            "details": "Requires documented failure of previous biotherapeutic therapies."
        }
        
        with patch("src.data.loader.get_case_details", return_value=mock_case):
            csv_path = generate_tracker_export(["88888"])
            
            try:
                self.assertTrue(os.path.exists(csv_path))
                
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f, delimiter=",")
                    rows = list(reader)
                    
                self.assertGreater(len(rows), 1)
                data_row = rows[1]
                
                # Check that CPT/HCPC Code column has J0897
                self.assertEqual(data_row[3], "J0897")
                
                # Check that fallback extraction expectation column uses HCPC label instead of CPT
                self.assertIn("HCPC: J0897", data_row[8])
                self.assertNotIn("CPT: J0897", data_row[8])
                
                # Check that fallback likelihood expectations column uses HCPC label instead of CPT
                self.assertIn("HCPC J0897", data_row[9])
                self.assertNotIn("CPT J0897", data_row[9])
                
            finally:
                try:
                    os.remove(csv_path)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
