#!/usr/bin/env python3
"""
Test script to verify medical coding extraction logic
"""
import re

# Sample AI response text (simulating what the AI would generate)
sample_case_explanation = """
Target Procedure: CPT 50360 - Renal Transplantation, Kidney Allotransplantation

This case involves a 45-year-old patient with end-stage renal disease requiring kidney transplantation.

CPT Codes Referenced:
- CPT 50360 - Renal Transplantation, Kidney Allotransplantation
- CPT 36800 - Arteriovenous Anastomosis for Hemodialysis Access
- CPT 93000 - Electrocardiogram, Complete

ICD-10 Codes:
- ICD-10: N18.6 - End Stage Renal Disease
- ICD-10: I10 - Essential Hypertension
- ICD-10: E11.22 - Type 2 Diabetes with Chronic Kidney Disease

Expected Outcome: PA Approval
"""

print("=" * 60)
print("TESTING MEDICAL CODING EXTRACTION")
print("=" * 60)

# Test 1: Extract target procedure
print("\n1. Testing Target Procedure Extraction:")
target_match = re.search(r'Target Procedure:\s*CPT\s*(\d+)\s*[-–]\s*([^\n]+)', sample_case_explanation, re.IGNORECASE)
if target_match:
    target_cpt = target_match.group(1).strip()
    target_cpt_desc = target_match.group(2).strip()
    print(f"   ✅ Target CPT: {target_cpt}")
    print(f"   ✅ Description: {target_cpt_desc}")
else:
    print("   ❌ No target procedure found!")

# Test 2: Extract all CPT codes
print("\n2. Testing All CPT Codes Extraction:")
cpt_matches = re.findall(r'CPT\s*(\d+)\s*[-–:]\s*([^\n,;]+)', sample_case_explanation, re.IGNORECASE)
print(f"   Found {len(cpt_matches)} CPT codes:")
for code, desc in cpt_matches:
    print(f"   ✅ {code.strip()} - {desc.strip()}")

# Test 3: Extract all ICD-10 codes
print("\n3. Testing ICD-10 Codes Extraction:")
icd_matches = re.findall(r'ICD[-\s]*10?\s*:?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\s*[-–:]\s*([^\n,;]+)', sample_case_explanation, re.IGNORECASE)
print(f"   Found {len(icd_matches)} ICD-10 codes:")
for code, desc in icd_matches:
    print(f"   ✅ {code.strip()} - {desc.strip()}")

print("\n" + "=" * 60)
print("EXTRACTION TEST COMPLETE")
print("=" * 60)

# Verify the extraction worked
if target_match and len(cpt_matches) >= 3 and len(icd_matches) >= 3:
    print("\n✅ ALL TESTS PASSED - Code extraction is working correctly!")
else:
    print("\n❌ SOME TESTS FAILED - Check the regex patterns")
