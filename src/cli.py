from . import workflow
from .data import loader as data_loader
from .core import patient_db
from .ai import client as ai_engine

_MODE_MAP = {
    "1": {"persona": True,  "reports": True,  "summary": True},
    "2": {"persona": False, "reports": True,  "summary": True},
    "3": {"persona": False, "reports": False, "summary": True},
    "4": {"persona": False, "reports": True,  "summary": False},
    "5": {"persona": True,  "reports": False, "summary": False},
    "":  {"persona": True,  "reports": True,  "summary": True},
}

_MODE_LABELS = {
    "1": "Persona + Reports + Summary (default)",
    "2": "Reports + Summary",
    "3": "Summary only",
    "4": "Reports only",
    "5": "Persona only",
}


def _prompt_generation_mode() -> dict:
    """Ask the user which document types to generate and return a mode dict."""
    print("\n📋 What to generate?")
    for k, label in _MODE_LABELS.items():
        marker = " (default)" if k == "1" else ""
        print(f"   [{k}] {label}{marker}")
    choice = input("   Choice [1]: ").strip()
    return _MODE_MAP.get(choice, _MODE_MAP[""])


def main():
    print("\n🚀 Clinical Data Generator — Modular & Interactive")

    if not ai_engine.check_connection():
        print("\n❌ AI connection failed. Check credentials/internet.")
        return

    while True:
        print("\n" + "=" * 60)
        print("🎯 Enter Patient ID  (or 	'*' for batch, 'q' to quit)")
        print("   💡 '225-fix CPT code'  → patient 225 with feedback")
        print("   💡 '221,222,223'       → comma-separated batch")
        target_input = input("   ID: ").strip()

        if not target_input:
            continue

        # ── QUIT ──────────────────────────────────────────────────────────────
        if target_input.lower() in {"q", "quit", "exit"}:
            print("\n👋 Goodbye!\n")
            break

        # ── PARSE FEEDBACK SUFFIX ──────────────────────────────────────────────
        feedback   = ""
        base_input = target_input
        if "-" in target_input and not target_input.startswith("--"):
            parts      = target_input.split("-", 1)
            base_input = parts[0].strip()
            feedback   = parts[1].strip()

        # ── BATCH: ALL PATIENTS ────────────────────────────────────────────────
        if base_input == "*":
            print("\n🔄 Batch mode: all patients…")
            all_ids       = data_loader.get_all_patient_ids()
            generation_mode = _prompt_generation_mode()
            current_names = patient_db.get_all_patient_names()
            processed = 0

            for p_id in all_ids:
                if workflow.check_patient_sync_status(p_id, generation_mode):
                    print(f"   ⏭️  Skipping {p_id} (already complete)")
                    continue
                print(f"\n▶️  Processing {p_id}…")
                new_name = workflow.process_patient_workflow(
                    p_id,
                    feedback=feedback,
                    excluded_names=current_names,
                    generation_mode=generation_mode,
                )
                if new_name:
                    current_names.append(new_name)
                processed += 1

            print(f"\n✅ Batch complete. Processed {processed} patient(s).")
            continue

        # ── BATCH: COMMA-SEPARATED ────────────────────────────────────────────
        if "," in base_input:
            patient_ids     = [pid.strip() for pid in base_input.split(",") if pid.strip()]
            generation_mode = _prompt_generation_mode()
            current_names   = patient_db.get_all_patient_names()

            for idx, p_id in enumerate(patient_ids, 1):
                print(f"\n▶️  [{idx}/{len(patient_ids)}] Patient {p_id}…")
                new_name = workflow.process_patient_workflow(
                    p_id,
                    feedback,
                    excluded_names=current_names,
                    generation_mode=generation_mode,
                )
                if new_name:
                    current_names.append(new_name)

            print(f"\n✅ Batch complete. {len(patient_ids)} patient(s) processed.")
            continue

        # ── SINGLE PATIENT ────────────────────────────────────────────────────
        p_id = base_input
        generation_mode = _prompt_generation_mode()

        if not feedback:
            print("\n💡 Feedback / Instructions (optional — press Enter to skip)")
            feedback = input("   > ").strip()

        current_names = patient_db.get_all_patient_names()
        workflow.process_patient_workflow(
            p_id,
            feedback,
            excluded_names=current_names,
            generation_mode=generation_mode,
        )

        if workflow.check_patient_sync_status(p_id, generation_mode):
            print("   ✅ Verification: documents present in output directories.")
