
import os

file_path = "/Users/akshaykumar/code/lucenz/pdgenerator/prompts.py"

with open(file_path, 'r') as f:
    content = f.read()

# 1. Update Report Metadata
target_metadata = """            DOB: (YYYY-MM-DD)
            REPORT_DATE: (YYYY-MM-DD from Timeline)"""
replacement_metadata = """            DOB: (YYYY-MM-DD)
            REPORT_DATE: (YYYY-MM-DD from Timeline)
            PROVIDER_NPI: (NPI from Persona)"""

if target_metadata in content:
    content = content.replace(target_metadata, replacement_metadata)
else:
    print("Metadata target not found")

# 2. Update Provider Instruction
target_provider = """          - `provider` (GP), `link` (N/A)"""
replacement_provider = """          - `provider` (GP), `link` (N/A)
          - **Provider NPI (MANDATORY)**: `provider.formatted_npi`: Format "XXXXXXXXXX" (10 digits)"""

if target_provider in content:
    content = content.replace(target_provider, replacement_provider)
else:
    print("Provider target not found")

# 3. Update Payer Section (Remove NPI from here, remove subscriber from other line)
# We need to be careful with exact whitespace
target_npi_payer = """            - `NPI`: Format "XXXXXXXXXX" (10 digits)\n"""
if target_npi_payer in content:
    content = content.replace(target_npi_payer, "")
else:
    print("Payer NPI target not found")

target_subscriber = """- All other payer fields (deductible, copay, effective_date, subscriber details)"""
replacement_subscriber = """- All other payer fields (deductible, copay, effective_date)"""

if target_subscriber in content:
    content = content.replace(target_subscriber, replacement_subscriber)
else:
    print("Subscriber details target not found")
    
# Remove group/subscriber fields if they exist in prompts (didn't see explicit group instruction in the view_file prompt earlier, but let me check)
# In view_file:
# 202:            - All other payer fields (deductible, copay, effective_date, subscriber details)
# I don't see group_id explicit instruction in the view_file output I saw earlier at lines 196-202.
# Wait, let me check lines 196-202 again.
# 196:          - **payer (MANDATORY - UnitedHealthcare ONLY)**:
# 197:            - `payer_name`: "UnitedHealthcare"
# 198:            - `plan_name`: "Medicare Advantage"
# 199:            - `plan_type`: "Medicare Advantage"
# 200:            - `NPI`: Format "XXXXXXXXXX" (10 digits)
# 201:            - `policy_number`: Format "POL-YYYY-XXXXXX" (year + 6 digits)
# 202:            - All other payer fields (deductible, copay, effective_date, subscriber details)

with open(file_path, 'w') as f:
    f.write(content)

print("Updates applied.")
