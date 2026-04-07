#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Tuple

# Ensure src/ is importable
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from core import patient_db  # noqa: E402
from core.config import get_patient_logs_folder, get_patient_records_folder  # noqa: E402


def _truncate(text: str, max_len: int) -> str:
    if max_len <= 0:
        return text
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + " ... (truncated)"


def _compact_value(value: Any, max_text: int, max_bio: int, key: str | None = None) -> Tuple[Any, int]:
    truncated = 0
    if isinstance(value, str):
        limit = max_bio if key == "bio_narrative" else max_text
        new_val = _truncate(value, limit)
        if new_val != value:
            truncated += 1
        return new_val, truncated
    if isinstance(value, list):
        new_list = []
        for item in value:
            new_item, t = _compact_value(item, max_text, max_bio, key=None)
            truncated += t
            new_list.append(new_item)
        return new_list, truncated
    if isinstance(value, dict):
        new_dict = {}
        for k, v in value.items():
            new_v, t = _compact_value(v, max_text, max_bio, key=str(k))
            truncated += t
            new_dict[k] = new_v
        return new_dict, truncated
    return value, truncated


def _compact_patient_db(
    data: Dict[str, Any],
    patient_ids: set[str],
    max_text: int,
    max_bio: int,
) -> Tuple[Dict[str, Any], int]:
    updated = 0
    for pid, record in data.items():
        if patient_ids and pid not in patient_ids:
            continue
        if not isinstance(record, dict):
            continue
        new_record, truncated = _compact_value(record, max_text, max_bio)
        if truncated:
            data[pid] = new_record
            updated += 1
    return data, updated


def _split_history_entries(text: str) -> list[str]:
    parts = re.split(r"\n-{10,}\n", text)
    return [p.strip() for p in parts if p.strip()]


def _compact_history_entry(entry: str, max_feedback: int, max_text: int) -> str:
    lines = entry.splitlines()
    compacted = []
    for line in lines:
        if line.startswith("USER FEEDBACK:"):
            val = line[len("USER FEEDBACK:"):].strip()
            compacted.append("USER FEEDBACK: " + _truncate(val, max_feedback))
        elif line.startswith("AI CHANGES:"):
            val = line[len("AI CHANGES:"):].strip()
            compacted.append("AI CHANGES: " + _truncate(val, max_text))
        else:
            compacted.append(line)
    return "\n".join(compacted)


def _compact_history_log(log_path: str, max_entries: int, max_feedback: int, max_text: int, dry_run: bool) -> bool:
    if not os.path.exists(log_path):
        return False
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    entries = _split_history_entries(content)
    if max_entries > 0:
        entries = entries[-max_entries:]
    entries = [_compact_history_entry(e, max_feedback, max_text) for e in entries]
    rebuilt = ""
    for entry in entries:
        rebuilt += "\n--------------------------------------------------\n" + entry.strip() + "\n"
    if rebuilt == content:
        return False
    if not dry_run:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(rebuilt)
    return True


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 10:
        return False
    return set(stripped) in [{"="}, {"─"}]


def _compact_patient_record_feedback(path: str, max_feedback: int, dry_run: bool) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "GENERATION FEEDBACK LOG" not in content:
        return False

    # Drop any appended "Earlier Feedback" section
    if "  ── Earlier Feedback ──" in content:
        content = content.split("  ── Earlier Feedback ──")[0].rstrip() + "\n"

    lines = content.splitlines()
    idx = next((i for i, l in enumerate(lines) if "GENERATION FEEDBACK LOG" in l), None)
    if idx is None:
        return False

    ts_idx = next((i for i in range(idx + 1, len(lines)) if "[" in lines[i] and "]" in lines[i]), None)
    if ts_idx is None:
        return False

    fb_start = ts_idx + 1
    fb_end = next((i for i in range(fb_start, len(lines)) if _is_separator(lines[i])), len(lines))
    fb_text = "\n".join(l.strip() for l in lines[fb_start:fb_end]).strip()
    fb_text = _truncate(fb_text, max_feedback) if fb_text else "(not recorded)"

    new_lines = lines[:fb_start] + [f"  {fb_text}"] + lines[fb_end:]
    new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")

    if new_content == content:
        return False
    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    return True


def _resolve_patient_ids(all_patients: bool, patient_id: str | None) -> set[str]:
    if all_patients:
        return set()
    if patient_id:
        return {str(patient_id)}
    raise SystemExit("Error: supply --patient-id or --all")


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
    patient_ids = _resolve_patient_ids(args.all, args.patient_id)

    # Compact patient DB
    patient_db._init_db()  # type: ignore[attr-defined]
    try:
        with open(patient_db.DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    data, updated = _compact_patient_db(data, patient_ids, args.max_text, args.max_bio)
    if updated and not args.dry_run:
        with open(patient_db.DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    print(f"DB compacted: {updated} patient record(s) updated.")

    # Compact history logs + patient record feedback
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

    print(f"History logs compacted: {hist_changed} file(s) updated.")
    print(f"Patient record feedback compacted: {rec_changed} file(s) updated.")


if __name__ == "__main__":
    main()
