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

class TestPriorAuthTracker(unittest.TestCase):
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
        """Verify that generate_tracker_export can execute without errors and generates files with 13 columns."""
        import csv
        # We can pass a dummy patient ID that does not exist to verify the fallback compilation logic
        pdf_path = generate_tracker_export(["99999"])
        self.assertTrue(os.path.exists(pdf_path))
        
        tsv_path = pdf_path.replace(".pdf", ".tsv")
        self.assertTrue(os.path.exists(tsv_path))
        
        # Verify the TSV columns match our 13-column schema exactly
        try:
            with open(tsv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                rows = list(reader)
                
                columns = rows[0]
                expected_columns = [
                    "Patient ID", "Patient Name", "DOB", "Department", "CPT Code",
                    "Procedure/Medicine Name", "Provider", "Insurance Type", "Policy Name",
                    "extraction expectation", "likelihood expectations", "attachments",
                    "post-attachment likelihood"
                ]
                
                self.assertEqual(len(columns), 13)
                self.assertEqual(columns, expected_columns)
                
                # Check data row format
                self.assertGreater(len(rows), 1)
                data_fields = rows[1]
                self.assertEqual(len(data_fields), 13)
                self.assertEqual(data_fields[0], "99999") # Patient ID
        except Exception as e:
            self.fail(f"TSV schema verification failed: {e}")
        
        # Clean up generated test outputs
        try:
            os.remove(pdf_path)
            os.remove(tsv_path)
        except Exception:
            pass

    def test_tracker_fallback_rich_fields(self):
        """Verify that fallback data fields are rich and contain no raw HTML tags in the TSV."""
        import csv
        pdf_path = generate_tracker_export(["99999"])
        tsv_path = pdf_path.replace(".pdf", ".tsv")
        
        try:
            with open(tsv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
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
            extraction = data_row[9]  # extraction expectation
            likelihood = data_row[10] # likelihood expectations
            post_likelihood = data_row[12] # post-attachment likelihood
            
            # Since patient 99999 is a dummy, it uses the fallback path
            self.assertIn("Expected Service:", extraction)
            self.assertIn("Required Criteria:", extraction)
            self.assertIn("likelihood of approval", likelihood.lower())
            self.assertIn("Likelihood", post_likelihood)
            
        finally:
            # Clean up generated test outputs
            try:
                os.remove(pdf_path)
                os.remove(tsv_path)
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
