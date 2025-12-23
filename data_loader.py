import os
import pandas as pd
import glob

INPUT_EXCEL = "core/UAT Plan.xlsx"
SQL_FOLDER = "sqls"
SCHEMA_PATH = "core/mockdata_schema.sql"
CORE_FOLDER = "core"

def _get_patient_id_column(df: pd.DataFrame) -> str:
    """Helper: Identifies the Patient ID column."""
    if 'Patient ID' in df.columns:
        return 'Patient ID'
    
    # Heuristic Search
    for col in df.columns:
        if 'Unnamed' in str(col):
            first_val = df[col].dropna().iloc[0] if not df[col].dropna().empty else 0
            if isinstance(first_val, (int, float)) and first_val > 100:
                return col
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
        with open(SCHEMA_PATH, 'r') as f:
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
            df.columns = df.columns.str.strip()
            
            if 'Test Case #' not in df.columns:
                continue
                
            if 'Test Case #' not in df.columns:
                continue
                
            id_col = _get_patient_id_column(df)
            
            # Iterate
            for _, row in df.iterrows():
                p_id = _normalize_id(row.get(id_col, ''))
                
                if p_id == target_id:
                    # Found Match
                    return {
                        "id": p_id,
                        "procedure": row.get('Procedure', 'Unknown'),
                        "outcome": row.get('Expected Result', 'Unknown'),
                        "details": row.get('Test Case Details', 'No details provided')
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
            df.columns = df.columns.str.strip()
            
            if 'Test Case #' not in df.columns:
                continue
                
            if 'Test Case #' not in df.columns:
                continue
                
            id_col = _get_patient_id_column(df)
            
            for _, row in df.iterrows():
                # Check for valid ID
                p_id = _normalize_id(row.get(id_col, ''))
                if p_id and p_id != '':
                     found_ids.add(p_id)
                    
        return sorted(list(found_ids))
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
    with open(path, 'w') as f:
        f.write(content)
    return path
