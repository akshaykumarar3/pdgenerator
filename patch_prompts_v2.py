
import os

file_path = "/Users/akshaykumar/code/lucenz/pdgenerator/prompts.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # 1. Metadata Block
    if "REPORT_DATE: (YYYY-MM-DD from Timeline)" in line:
        new_lines.append(line)
        # Add the new line if not already there
        if "PROVIDER_NPI:" not in lines[i+1]:
            new_lines.append("           PROVIDER_NPI: (NPI from Persona)\n")
        continue

    # 2. Provider Instruction
    if "- `provider` (GP), `link` (N/A)" in line:
        new_lines.append(line)
        if "Provider NPI (MANDATORY)" not in lines[i+1]:
            new_lines.append("         - **Provider NPI (MANDATORY)**: `provider.formatted_npi`: Format \"XXXXXXXXXX\" (10 digits)\n")
        continue

    # 3. Payer NPI Removal
    if "- `NPI`: Format \"XXXXXXXXXX\" (10 digits)" in line:
        # Check context if it's in Payer section (around line 200)
        # To be safe, we just skip it if it's indented like that, assuming it's the one in Payer 
        # (The provider one we just added has different text "Provider NPI")
        continue
        
    # 4. Subscriber Removal from Payer fields (already done? check content)
    # The previous run seemed to have removed it: 'All other payer fields (deductible, copay, effective_date)\n'
    # So we don't need to do anything if it's already clean.
    
    new_lines.append(line)

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print("Updates applied via line iteration.")
