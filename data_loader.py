import os
import re
import json
import datetime
import pandas as pd
import glob

# Use absolute paths relative to project root for resource files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_EXCEL = os.path.join(BASE_DIR, "core", "UAT Plan.xlsx")
SQL_FOLDER = os.path.join(BASE_DIR, "sqls")
SCHEMA_PATH = os.path.join(BASE_DIR, "core", "mockdata_schema.sql")
CORE_FOLDER = os.path.join(BASE_DIR, "core")
CPT_MAP_PATH = os.path.join(BASE_DIR, "core", "cpt_code_map.json")


def _normalize_text(val) -> str:
    try:
        return str(val).strip()
    except Exception:
        return ""


def _extract_cpt_code(*values) -> str:
    """Try to extract a 5-digit CPT code from any provided value."""
    for v in values:
        text = _normalize_text(v)
        if not text:
            continue
        m = re.search(r"\b(\d{5})\b", text)
        if m:
            return m.group(1)
    return ""


def refresh_cpt_code_map() -> dict:
    """
    Build a CPT code mapping from the UAT Plan and persist to core/cpt_code_map.json.
    Returns the mapping dict.
    """
    mapping = {"by_code": {}, "by_procedure": {}, "updated_at": datetime.datetime.now().isoformat()}
    if not os.path.exists(INPUT_EXCEL):
        return mapping

    try:
        xl = pd.ExcelFile(INPUT_EXCEL)
        for sheet in xl.sheet_names:
            df = pd.read_excel(INPUT_EXCEL, sheet_name=sheet)
            df.columns = df.columns.astype(str).str.strip()

            cols_to_ffill = ['Test Case #', 'Department', 'CPT Code', 'Procedure', 'Code', 'Test Case Details']
            existing_cols = [c for c in cols_to_ffill if c in df.columns]
            if existing_cols:
                df[existing_cols] = df[existing_cols].ffill()

            for _, row in df.iterrows():
                procedure = _normalize_text(row.get('Procedure', '')) or _normalize_text(row.get('Code', ''))
                cpt_code = _extract_cpt_code(row.get('CPT Code', ''), procedure, row.get('Test Case Details', ''))
                if not cpt_code:
                    continue

                department = _normalize_text(row.get('Department', ''))
                test_case = _normalize_text(row.get('Test Case #', ''))

                if cpt_code not in mapping["by_code"]:
                    mapping["by_code"][cpt_code] = {
                        "procedure": procedure,
                        "department": department,
                        "test_case": test_case
                    }

                proc_key = procedure.lower()
                if proc_key and proc_key not in mapping["by_procedure"]:
                    mapping["by_procedure"][proc_key] = cpt_code

        with open(CPT_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)

    except Exception as e:
        print(f"Error building CPT map: {e}")

    return mapping


def get_cpt_code_map() -> dict:
    if os.path.exists(CPT_MAP_PATH):
        try:
            with open(CPT_MAP_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _get_patient_id_column(df: pd.DataFrame) -> str:
    """Helper: Identifies the Patient ID column."""
    if 'Patient ID' in df.columns:
        return 'Patient ID'
    
    # Heuristic Search (Look for 'Unnamed' column with numeric IDs > 100)
    for col in df.columns:
        if 'Unnamed' in str(col):
            # Check the first 5 non-null values
            valid_vals = df[col].dropna().head(5)
            for val in valid_vals:
                try:
                    num = int(float(val))
                    if num > 100:
                        return col
                except (ValueError, TypeError):
                    continue
    return 'Patient ID' # Default fallback

def _normalize_id(raw_val) -> str:
    """Helper: Standardizes Patient ID format."""
    try:
        return str(int(float(raw_val)))
    except:
        return str(raw_val).strip()

def get_db_schema():
    """Reads the schema file."""
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def load_patient_case(target_id: str):
    """
    Scans the Excel file (all sheets) for the specific Patient ID.
    Returns a dictionary of case details or None if not found.
    """
    if not os.path.exists(INPUT_EXCEL):
        raise FileNotFoundError(f"Excel file {INPUT_EXCEL} not found.")

    try:
        xl = pd.ExcelFile(INPUT_EXCEL)
        for sheet in xl.sheet_names:
            df = pd.read_excel(INPUT_EXCEL, sheet_name=sheet)
            df.columns = df.columns.astype(str).str.strip()
            
            # Forward-fill specifically for merged columns (Test Case #, Procedure, Code, Details)
            cols_to_ffill = ['Test Case #', 'Department', 'CPT Code', 'Procedure', 'Code', 'Test Case Details']
            existing_cols = [c for c in cols_to_ffill if c in df.columns]
            if existing_cols:
                df[existing_cols] = df[existing_cols].ffill()
            
            id_col = _get_patient_id_column(df)
            if id_col not in df.columns:
                continue
            
            # Iterate
            for _, row in df.iterrows():
                p_id = _normalize_id(row.get(id_col, ''))
                
                if p_id == str(target_id):
                    # Found Match
                    procedure = str(row.get('Procedure', '')) or str(row.get('Code', 'Unknown'))
                    if not procedure.strip(): procedure = "Unknown"
                    cpt_code = _extract_cpt_code(row.get('CPT Code', ''), procedure, row.get('Test Case Details', ''))
                        
                    return {
                        "id": p_id,
                        "procedure": procedure,
                        "cpt_code": cpt_code,
                        "outcome": str(row.get('Expected Result', 'Unknown')),
                        "details": str(row.get('Test Case Details', 'No details provided'))
                    }
        return None

    except Exception as e:
        print(f"Error reading Excel: {e}")
        return None

def get_all_patient_ids() -> list:
    """
    Scans the Excel file and returns a sorted list of ALL valid patient IDs found.
    """
    found_ids = set()
    if not os.path.exists(INPUT_EXCEL):
        return []

    try:
        xl = pd.ExcelFile(INPUT_EXCEL)
        for sheet in xl.sheet_names:
            df = pd.read_excel(INPUT_EXCEL, sheet_name=sheet)
            df.columns = df.columns.astype(str).str.strip()
            
            # Forward-fill specifically for merged columns
            cols_to_ffill = ['Test Case #', 'Department', 'CPT Code', 'Procedure', 'Code', 'Test Case Details']
            existing_cols = [c for c in cols_to_ffill if c in df.columns]
            if existing_cols:
                df[existing_cols] = df[existing_cols].ffill()
            
            id_col = _get_patient_id_column(df)
            if id_col not in df.columns:
                continue
            
            for _, row in df.iterrows():
                # Check for valid ID
                p_id = _normalize_id(row.get(id_col, ''))
                if p_id and str(p_id).lower() not in ['nan', 'none', '']:
                    found_ids.add(p_id)
                    
        def sort_key(x):
            try: return int(x)
            except: return float('inf')
            
        return sorted(list(found_ids), key=sort_key)
    except Exception as e:
        print(f"Error scanning IDs: {e}")
        return []

def find_sql_file(patient_id: str):
    """
    Locates the source SQL file for the patient using fuzzy matching.
    Returns absolute path or None.
    """
    if not os.path.exists(SQL_FOLDER):
        return None
        
    target_filename = f"Patient {patient_id} Summary.sql"
    
    # Case insensitive search
    files = os.listdir(SQL_FOLDER)
    for f in files:
        if f.lower() == target_filename.lower():
            return os.path.join(SQL_FOLDER, f)
            
    # Fallback
    for f in files:
         if f.lower() == f"patient {patient_id}.sql" or f.lower() == f"{patient_id}.sql":
             return os.path.join(SQL_FOLDER, f)
             
    return None

def get_template_sql():
    """
    Returns the absolute path to ANY valid SQL file to use as a template.
    Priorities:
    1. core/seed_template.sql (The Golden Seed)
    2. sqls/*_final.sql (Existing generated patients)
    3. sqls/*.sql (Any other SQL)
    """
    # 1. Check Core Seed
    seed_path = os.path.join(CORE_FOLDER, "seed_template.sql")
    if os.path.exists(seed_path):
        return seed_path

    # 2. Check Generated Files
    if not os.path.exists(SQL_FOLDER):
        return None
        
    all_files = [f for f in os.listdir(SQL_FOLDER) if f.endswith('.sql')]
    if not all_files:
        return None
        
    # Prefer a known good template if possible
    final_files = [f for f in all_files if '_final.sql' in f]
    if final_files:
        return os.path.join(SQL_FOLDER, final_files[0])
        
    return os.path.join(SQL_FOLDER, all_files[0])

def save_sql(patient_id: str, content: str, output_folder: str = SQL_FOLDER):
    """Saves the final SQL."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)
        
    filename = f"{patient_id}_final.sql"
    path = os.path.join(output_folder, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path
