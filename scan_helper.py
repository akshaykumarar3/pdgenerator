import os

def scan_existing_documents(patient_id: str, report_folder: str) -> tuple[int, dict]:
    """
    Scans the patient's report folder for existing PDF documents.
    Returns:
        max_seq (int): The highest sequence number found (e.g., 5 for DOC-210-005...).
        existing_docs_map (dict): A map of {Title: {"seq": int, "filename": str}} for smart updates.
    """
    existing_filenames = []
    max_seq = 0
    existing_docs_map = {} 
    
    if os.path.exists(report_folder):
        for f in os.listdir(report_folder):
            if f.endswith(".pdf") and f.startswith(f"DOC-{patient_id}-"):
                existing_filenames.append(f)
                try:
                    # Remove extension
                    name = os.path.splitext(f)[0]
                    parts = name.split("-")
                    # Expected format: DOC-{PID}-{SEQ}-{Title Part 1}-{Title Part 2}...
                    if len(parts) >= 4:
                        seq_num = int(parts[2])
                        
                        # Reconstruct title from parts[3:]
                        title_extracted = "-".join(parts[3:])
                        
                        # Remove -NAF suffix if present for clean matching
                        if title_extracted.endswith("-NAF"):
                            title_extracted = title_extracted[:-4]
                            
                        existing_docs_map[title_extracted] = {"seq": seq_num, "filename": f}
                        
                        if seq_num > max_seq:
                            max_seq = seq_num
                except Exception:
                    # Silently ignore malformed filenames
                    pass
                    
    return max_seq, existing_docs_map
