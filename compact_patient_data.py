#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Tuple

# ─── PATH & DEPENDENCY SETUP ──────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(PROJECT_ROOT, "cred", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

try:
    from core import patient_db
    from core.config import get_patient_logs_folder, get_patient_records_folder, OUTPUT_DIR
except ImportError as e:
    print(f"❌ Critical Error: Could not import core components ({e})")
    print("   Please ensure you are running this from the project root within the virtual environment.")
    sys.exit(1)


# ─── UTILITIES ────────────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int) -> str:
    """Truncates text to max_len and adds a suffix if needed."""
    if not text or max_len <= 0:
        return text
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + " ... (truncated)"


def _compact_value(value: Any, max_text: int, max_bio: int, key: str | None = None) -> Tuple[Any, int]:
    """Recursively compacts strings in a JSON-like object."""
    truncated_count = 0
    if isinstance(value, str):
        limit = max_bio if key == "bio_narrative" else max_text
        new_val = _truncate(value, limit)
        if new_val != value:
            truncated_count += 1
        return new_val, truncated_count
    
    if isinstance(value, list):
        new_list = []
        for item in value:
            new_item, t = _compact_value(item, max_text, max_bio)
            truncated_count += t
            new_list.append(new_item)
        return new_list, truncated_count
    
    if isinstance(value, dict):
        new_dict = {}
        for k, v in value.items():
            new_v, t = _compact_value(v, max_text, max_bio, key=str(k))
            truncated_count += t
            new_dict[k] = new_v
        return new_dict, truncated_count
    
    return value, truncated_count


# ─── LOG COMPACTION ────────────────────────────────────────────────────────────

def _split_history_entries(text: str) -> list[str]:
    """Splits history log by the standard separator line."""
    parts = re.split(r"\n?-{10,}\n?", text)
    return [p.strip() for p in parts if p.strip()]


def _compact_history_entry(entry: str, max_feedback: int, max_text: int) -> str:
    """Truncates specific blocks within a single history entry."""
    lines = entry.splitlines()
    compacted = []
    for line in lines:
        if line.startswith("USER FEEDBACK:"):
            val = line[len("USER FEEDBACK:"):].strip()
            compacted.append(f"USER FEEDBACK: {_truncate(val, max_feedback)}")
        elif line.startswith("AI CHANGES:"):
            val = line[len("AI CHANGES:"):].strip()
            compacted.append(f"AI CHANGES: {_truncate(val, max_text)}")
        else:
            compacted.append(line)
    return "\n".join(compacted)


def _compact_history_log(log_path: str, max_entries: int, max_feedback: int, max_text: int, dry_run: bool) -> bool:
    """Reads, compacts, and optionally writes a patient history log."""
    if not os.path.exists(log_path):
        return False
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    entries = _split_history_entries(content)
    if not entries:
        return False

    if max_entries > 0 and len(entries) > max_entries:
        entries = entries[-max_entries:]

    compacted_entries = [_compact_history_entry(e, max_feedback, max_text) for e in entries]
    
    sep = "\n" + "-" * 50 + "\n"
    rebuilt = sep + (sep.join(compacted_entries)) + "\n"

    if rebuilt.strip() == content.strip():
        return False

    if not dry_run:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(rebuilt)
    return True


# ─── RECORD COMPACTION ─────────────────────────────────────────────────────────

def _is_hr(line: str) -> bool:
    """Checks if a line is a horizontal separator (= or - or \u2500)."""
    stripped = line.strip()
    return len(stripped) >= 10 and all(c in "=-─" for c in stripped)


def _compact_patient_record_feedback(path: str, max_feedback: int, dry_run: bool) -> bool:
    """
    Specifically targets the 'GENERATION FEEDBACK LOG' section in -record.txt.
    Prunes 'Earlier Feedback' completely and truncates the current block.
    """
    if not os.path.exists(path):
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    if "GENERATION FEEDBACK LOG" not in content:
        return False

    # 1. Strip all "Earlier Feedback" to prevent infinite growth
    # Uses a broad pattern to match dashes or spaces around the text
    split_parts = re.split(r"\s*[─-]+ Earlier Feedback [─-]+\s*", content, flags=re.IGNORECASE)
    content = split_parts[0].rstrip() + "\n"

    lines = content.splitlines()
    new_lines = []
    in_feedback_block = False
    
    for line in lines:
        if "GENERATION FEEDBACK LOG" in line:
            new_lines.append(line)
            in_feedback_block = True
            continue
        
        if in_feedback_block:
            s_line = line.strip()
            # If we hit another section or a separator, we are done with the block
            if _is_hr(line) and len(new_lines) > 5:
                in_feedback_block = False
                new_lines.append(line)
                continue
                
            # If it's a content line (indented, not a timestamp), truncate it
            if s_line and not s_line.startswith("[") and not _is_hr(line):
                indented_fb = s_line
                truncated_fb = _truncate(indented_fb, max_feedback)
                new_lines.append(f"  {truncated_fb}")
                # We typically only have one feedback block per run, so we can stop tracking after truncation
                in_feedback_block = False 
                continue
            
            new_lines.append(line)
        else:
            new_lines.append(line)

    new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")

    if new_content.strip() == content.strip():
        # Check if the split already changed the content
        if len(split_parts) == 1:
            return False

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    return True


# ─── DATA COMPACTION ───────────────────────────────────────────────────────────

def _compact_patient_db(data: Dict[str, Any], patient_ids: set[str], max_text: int, max_bio: int) -> Tuple[Dict[str, Any], int]:
    updated_count = 0
    for pid, record in data.items():
        if patient_ids and pid not in patient_ids:
            continue
        if not isinstance(record, dict):
            continue
        new_record, truncated = _compact_value(record, max_text, max_bio)
        if truncated:
            data[pid] = new_record
            updated_count += 1
    return data, updated_count


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def _resolve_patient_ids(all_patients: bool, patient_id: str | None) -> set[str]:
    if all_patients:
        return set()
    if patient_id:
        return {str(patient_id)}
    raise SystemExit("Error: Supply --patient-id or --all")


def main():
    parser = argparse.ArgumentParser(description="Compact patient DB text, history context, and feedback logs.")
    parser.add_argument("--patient-id", help="Patient ID to compact.")
    parser.add_argument("--all", action="store_true", help="Compact all patients in the DB.")
    parser.add_argument("--max-text", type=int, default=1200, help="Max chars for long text fields.")
    parser.add_argument("--max-bio", type=int, default=1200, help="Max chars for bio_narrative.")
    parser.add_argument("--max-feedback", type=int, default=800, help="Max chars for feedback blocks.")
    parser.add_argument("--history-entries", type=int, default=5, help="How many history entries to keep.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")

    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 RUNNING IN DRY-RUN MODE (No files will be modified)")

    try:
        patient_ids = _resolve_patient_ids(args.all, args.patient_id)
    except SystemExit as e:
        parser.print_help()
        sys.exit(1)

    # 1. Compact patient DB
    patient_db._init_db()
    try:
        with open(patient_db.DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        print(f"⚠️  Could not read patient DB at {patient_db.DB_PATH}")
        data = {}

    if isinstance(data, dict):
        data, updated = _compact_patient_db(data, patient_ids, args.max_text, args.max_bio)
        if updated and not args.dry_run:
            with open(patient_db.DB_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        print(f"✅ DB compacted: {updated} patient record(s) updated.")
    else:
        print("⚠️  Invalid DB format; skipping DB compaction.")

    # 2. Compact history logs + patient record feedback
    targets = patient_ids or set(data.keys())
    hist_changed = 0
    rec_changed = 0
    
    for pid in sorted(targets):
        # Log compaction
        log_dir = get_patient_logs_folder(pid)
        log_path = os.path.join(log_dir, f"{pid}.txt")
        if _compact_history_log(log_path, args.history_entries, args.max_feedback, args.max_text, args.dry_run):
            hist_changed += 1

        # Patient record feedback log compaction
        rec_dir = get_patient_records_folder(pid)
        rec_path = os.path.join(rec_dir, f"{pid}-record.txt")
        if _compact_patient_record_feedback(rec_path, args.max_feedback, args.dry_run):
            rec_changed += 1

    print(f"✅ History logs compacted: {hist_changed} file(s) updated.")
    print(f"✅ Patient record feedback compacted: {rec_changed} file(s) updated.")


if __name__ == "__main__":
    main()
