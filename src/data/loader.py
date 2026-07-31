import os
import re
import json
import datetime
import pandas as pd

# Use absolute paths relative to project root for resource files
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
CORE_FOLDER = os.path.join(PROJECT_ROOT, "core")
INPUT_EXCEL = os.path.join(CORE_FOLDER, "UAT Plan.xlsx")
CPT_MAP_PATH = os.path.join(CORE_FOLDER, "cpt_code_map.json")

def get_repository():
    """Get the configured patient repository (JSON or Postgres)."""
    backend = os.getenv("PATIENT_STORAGE_BACKEND", "json").strip().lower()
    if backend == "postgres":
        from src.core.postgres_repository import PostgresPatientRepository
        return PostgresPatientRepository()
    else:
        from src.core.json_repository import JSONPatientRepository
        return JSONPatientRepository()



def _normalize_text(val) -> str:
    try:
        return str(val).strip()
    except Exception:
        return ""


def _extract_cpt_code(*values: str) -> str:
    """Try to extract a 5-digit CPT code or HCPCS code (e.g. J0897, Q5124) from any provided value.
    If regex search fails, falls back to mapping by procedure name in cpt_code_map.json.
    """
    for v in values:
        text = _normalize_text(v)
        if not text:
            continue
        # Check for HCPCS code first (letter followed by 4 digits, like J0897 or Q5124)
        m_hcpcs = re.search(r"\b([A-Za-z]\d{4})\b", text)
        if m_hcpcs:
            return m_hcpcs.group(1).upper()
        # Fallback to standard 5-digit CPT code
        m_cpt = re.search(r"\b(\d{5})\b", text)
        if m_cpt:
            return m_cpt.group(1)
            
    # Fallback to cpt_code_map.json lookup by procedure/text name
    cpt_map = get_cpt_code_map()
    by_procedure = cpt_map.get("by_procedure", {})
    for v in values:
        text = _normalize_text(v).lower().strip()
        if text in by_procedure:
            return by_procedure[text]
    return ""


def refresh_cpt_code_map() -> dict:
    """
    Build a CPT code mapping from the UAT Plan and persist to core/cpt_code_map.json
    and PostgreSQL if active.
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
                cpt_code = _extract_cpt_code(row.get('CPT Code', ''), row.get('Code', ''), procedure, row.get('Test Case Details', ''))
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

        backend = os.getenv("PATIENT_STORAGE_BACKEND", "json").strip().lower()
        if backend == "postgres":
            try:
                from core.postgres_repository import PostgresPatientRepository
                PostgresPatientRepository().save_cpt_code_map(mapping)
            except Exception:
                pass

    except Exception as e:
        print(f"Error building CPT map: {e}")

    return mapping


def get_cpt_code_map() -> dict:
    """Load CPT code map from the active repository."""
    repo = get_repository()
    cpt_map = repo.load_cpt_code_map()
    if cpt_map and cpt_map.get("by_code"):
        return cpt_map
    return {"by_code": {}, "by_procedure": {}, "updated_at": ""}


def _get_patient_id_column(df: pd.DataFrame) -> str:
    """Helper: Identifies the Patient ID column."""
    if 'Patient ID' in df.columns:
        return 'Patient ID'
    
    # Heuristic Search (Look for 'Unnamed' column with numeric IDs >= 1)
    for col in df.columns:
        if 'Unnamed' in str(col):
            # Check the first 5 non-null values
            valid_vals = df[col].dropna().head(5)
            for val in valid_vals:
                try:
                    num = int(float(val))
                    if num >= 1:
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
                    cpt_code = _extract_cpt_code(row.get('CPT Code', ''), row.get('Code', ''), procedure, row.get('Test Case Details', ''))
                    if not cpt_code:
                        print(f"[DEBUG] CPT extraction failed for patient {p_id}. "
                              f"Attempted values: CPT Code={row.get('CPT Code')}, Code={row.get('Code')}, "
                              f"procedure={procedure}, details={row.get('Test Case Details')}")
                    department = _normalize_text(row.get('Department', ''))
                    test_case_number = _normalize_text(row.get('Test Case #', ''))
                    expected_outcome = _normalize_text(row.get('Expected Result', 'Unknown'))
                    details = _normalize_text(row.get('Test Case Details', 'No details provided'))

                    return {
                        "id": p_id,
                        "test_case_number": test_case_number,
                        "department": department,
                        "procedure": procedure,
                        "cpt_code": cpt_code,
                        "outcome": expected_outcome,
                        "details": details,
                    }
        return None

    except Exception as e:
        print(f"Error reading Excel: {e}")
        return None


def get_case_details(patient_id: str) -> dict | None:
    """Public alias for load_patient_case — returns UAT case info for a patient ID."""
    return load_patient_case(patient_id)


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
