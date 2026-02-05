#!/usr/bin/env python3
"""
Dry run test script for PDF generator
Tests the new duplicate detection and default generation mode
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

import data_loader
import generator

def main():
    print("=" * 60)
    print("PDF GENERATOR DRY RUN TEST")
    print("=" * 60)
    
    # Get available patient IDs
    all_ids = data_loader.get_all_patient_ids()
    print(f"\n📋 Available Patient IDs: {all_ids[:10]}")
    
    if not all_ids:
        print("❌ No patient IDs found in Excel file!")
        return
    
    # Use first available ID for testing
    test_id = all_ids[0]
    print(f"\n🧪 Testing with Patient ID: {test_id}")
    
    # Load case data to verify
    case_data = data_loader.load_patient_case(test_id)
    if not case_data:
        print(f"❌ Could not load case data for Patient ID: {test_id}")
        return
    
    print(f"✅ Case Data Loaded:")
    print(f"   - Procedure: {case_data['procedure']}")
    print(f"   - Expected Result: {case_data['outcome']}")
    
    # Test with default generation mode (should be Persona + Reports + Summary)
    print(f"\n🚀 Running generator with DEFAULT mode (Persona + Reports + Summary)...")
    print(f"   This will test:")
    print(f"   - Smart duplicate detection")
    print(f"   - New default generation mode")
    print(f"   - Document creation workflow")
    
    try:
        result = generator.process_patient_workflow(
            patient_id=test_id,
            feedback="",
            excluded_names=[],
            generation_mode=None  # Use default
        )
        
        if result:
            print(f"\n✅ DRY RUN SUCCESSFUL!")
            print(f"   Generated patient: {result}")
        else:
            print(f"\n⚠️  Workflow completed but no patient name returned")
            
    except Exception as e:
        print(f"\n❌ DRY RUN FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("DRY RUN TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
