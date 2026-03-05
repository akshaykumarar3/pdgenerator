"""
PD Generator - Flask API Server
Exposes the clinical data generator as a REST API for the HTML UI.
"""
import os
import sys
import uuid
import threading
import traceback
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ─── Bootstrap: ensure the generator package is importable ───────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ─── Load env early (same as generator.py) ───────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "cred", ".env"))

import data_loader
import core.patient_db as patient_db

app = Flask(__name__)
CORS(app)  # Allow all origins so the file:// UI can call us

# ─── In-memory job store ──────────────────────────────────────────────────────
# { job_id: { status, logs: [], error, result } }
_jobs: dict = {}
_jobs_lock = threading.Lock()

OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "generated_output")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "patient-reports")
PERSONA_DIR = os.path.join(OUTPUT_DIR, "persona")
SUMMARY_DIR = os.path.join(OUTPUT_DIR, "summary")


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class JobLogger:
    """Captures print() output for a job and stores it line-by-line."""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self._real_stdout = sys.stdout

    def write(self, text: str):
        self._real_stdout.write(text)
        self._real_stdout.flush()
        if text.strip():
            with _jobs_lock:
                _jobs[self.job_id]["logs"].append(text.rstrip())

    def flush(self):
        self._real_stdout.flush()

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, *args):
        sys.stdout = self._real_stdout


def _run_generation(job_id: str, patient_id: str, feedback: str,
                     generation_mode: dict, pa_optimize: bool,
                     medications: list, allergies: list,
                     vaccinations: list, therapies: list,
                     behavioral_notes: str):
    """Background worker: calls the generator and updates job state."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"

    try:
        with JobLogger(job_id):
            import generator as gen

            # Build enriched feedback block
            extra_blocks = []
            if medications:
                med_lines = []
                for m in medications:
                    status_str = m.get("status", "current").upper()
                    med_lines.append(
                        f"  - [{status_str}] {m.get('brand','')} ({m.get('generic_name','')}) "
                        f"{m.get('dosage','')} | Qty: {m.get('qty','')} | "
                        f"Prescribed by: {m.get('prescribed_by','')} | "
                        f"Start: {m.get('start_date','')} End: {m.get('end_date','ongoing')} | "
                        f"Reason: {m.get('reason','')}"
                    )
                extra_blocks.append("MEDICATIONS (use exactly as provided):\n" + "\n".join(med_lines))

            if allergies:
                allergy_lines = []
                for a in allergies:
                    allergy_lines.append(
                        f"  - {a.get('allergen','')} | Type: {a.get('allergy_type','')} | "
                        f"Reaction: {a.get('reaction','')} | Severity: {a.get('severity','')} | "
                        f"Onset: {a.get('onset_date','')}"
                    )
                extra_blocks.append("ALLERGIES (use exactly as provided):\n" + "\n".join(allergy_lines))

            if vaccinations:
                vax_lines = []
                for v in vaccinations:
                    vax_lines.append(
                        f"  - {v.get('vaccine_name','')} | Type: {v.get('vaccine_type','')} | "
                        f"Date: {v.get('date_administered','')} | "
                        f"By: {v.get('administered_by','')} | Dose: {v.get('dose_number','1')} | "
                        f"Reason: {v.get('reason','')}"
                    )
                extra_blocks.append("VACCINATIONS (use exactly as provided):\n" + "\n".join(vax_lines))

            if therapies:
                therapy_lines = []
                for t in therapies:
                    therapy_lines.append(
                        f"  - [{t.get('status','active').upper()}] {t.get('therapy_type','')} Therapy | "
                        f"Provider: {t.get('provider','')} @ {t.get('facility','')} | "
                        f"Frequency: {t.get('frequency','')} | "
                        f"Start: {t.get('start_date','')} End: {t.get('end_date','ongoing')} | "
                        f"Reason: {t.get('reason','')} | Notes: {t.get('notes','')}"
                    )
                extra_blocks.append("THERAPY HISTORY (use exactly as provided):\n" + "\n".join(therapy_lines))

            if behavioral_notes:
                extra_blocks.append(f"BEHAVIORAL NOTES:\n  {behavioral_notes}")

            if pa_optimize:
                extra_blocks.append(
                    "PA APPROVAL OPTIMIZATION: Even if clinical outcome is expected denial/low-probability, "
                    "generate all clinical documents with the STRONGEST possible medical justification to "
                    "maximize PA approval probability. Include thorough clinical rationale, all supporting "
                    "evidence, and comprehensive documentation. The annotator summary will still note the "
                    "expected outcome label."
                )

            combined_feedback = feedback.strip()
            if extra_blocks:
                combined_feedback += ("\n\n" if combined_feedback else "") + "\n\n".join(extra_blocks)

            # Fetch exclusion names
            current_names = patient_db.get_all_patient_names()

            result_name = gen.process_patient_workflow(
                patient_id=patient_id,
                feedback=combined_feedback,
                excluded_names=current_names,
                generation_mode=generation_mode
            )

        # Capture changes_summary from AI result if accessible via history
        changes_summary = None
        try:
            import history_manager
            hist = history_manager.get_history(patient_id)
            if hist:
                # Last entry in history has the changes_summary
                lines = [l for l in hist.strip().split('\n') if l.strip()]
                # Find the summary block (comes after === markers)
                in_summary = False
                summary_lines = []
                for line in lines:
                    if 'Changes Summary:' in line or 'Summary:' in line:
                        in_summary = True
                        continue
                    if in_summary and line.startswith('==='):
                        break
                    if in_summary:
                        summary_lines.append(line)
                if summary_lines:
                    changes_summary = '\n'.join(summary_lines)
        except Exception:
            pass

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = result_name
            _jobs[job_id]["changes_summary"] = changes_summary

    except Exception as exc:
        err_msg = f"ERROR: {exc}\n{traceback.format_exc()}"
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = err_msg
            _jobs[job_id]["logs"].append(f"❌ {err_msg}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    """Health check."""
    return jsonify({"ok": True, "timestamp": datetime.now().isoformat()})


@app.route("/api/patients")
def api_patients():
    """Return all patient IDs from the Excel plan."""
    try:
        ids = data_loader.get_all_patient_ids()
        return jsonify({"patients": ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/patient/<patient_id>")
def api_get_patient(patient_id: str):
    """Return the current DB record for a patient (if it exists)."""
    record = patient_db.load_patient(patient_id)
    if record:
        return jsonify({"found": True, "data": record})
    return jsonify({"found": False, "data": None})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Spawn a background generation job. Returns job_id immediately."""
    body = request.get_json(force=True) or {}
    patient_id     = str(body.get("patient_id", "")).strip()
    feedback       = body.get("feedback", "")
    generation_mode = body.get("generation_mode", {"summary": True, "reports": True, "persona": True})
    pa_optimize    = bool(body.get("pa_optimize", False))
    medications    = body.get("medications", [])
    allergies      = body.get("allergies", [])
    vaccinations   = body.get("vaccinations", [])
    therapies      = body.get("therapies", [])
    behavioral_notes = body.get("behavioral_notes", "")

    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "logs": [f"🚀 Job {job_id} queued for patient {patient_id}"],
            "error": None,
            "result": None,
            "changes_summary": None,
            "patient_id": patient_id,
            "created_at": datetime.now().isoformat(),
            # Store request context for the post-generation summary
            "request_context": {
                "feedback": feedback,
                "generation_mode": generation_mode,
                "pa_optimize": pa_optimize,
                "medication_count": len(medications),
                "allergy_count": len(allergies),
                "vaccination_count": len(vaccinations),
                "therapy_count": len(therapies),
                "has_behavioral_notes": bool(behavioral_notes),
            }
        }

    t = threading.Thread(
        target=_run_generation,
        args=(job_id, patient_id, feedback, generation_mode, pa_optimize,
              medications, allergies, vaccinations, therapies, behavioral_notes),
        daemon=True
    )
    t.start()

    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/job/<job_id>")
def api_job_status(job_id: str):
    """Poll job status + latest log lines."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Support since_index to avoid re-sending old logs
    since = request.args.get("since", 0, type=int)
    new_logs = job["logs"][since:]

    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "logs": new_logs,
        "log_total": len(job["logs"]),
        "error": job.get("error"),
        "result": job.get("result"),
        "patient_id": job.get("patient_id"),
        "changes_summary": job.get("changes_summary"),
        "request_context": job.get("request_context", {}),
        "all_logs": job["logs"],  # Full log for summary panel
    })


@app.route("/api/output/<patient_id>")
def api_output(patient_id: str):
    """List all generated output files for a patient."""
    files = []

    # Reports
    report_folder = os.path.join(REPORTS_DIR, patient_id)
    if os.path.exists(report_folder):
        for f in sorted(os.listdir(report_folder)):
            if f.endswith(".pdf"):
                files.append({"type": "report", "name": f,
                               "path": os.path.join(report_folder, f)})

    # Persona
    if os.path.exists(PERSONA_DIR):
        for f in sorted(os.listdir(PERSONA_DIR)):
            if f.startswith(f"PERSONA-{patient_id}") and f.endswith(".pdf"):
                files.append({"type": "persona", "name": f,
                               "path": os.path.join(PERSONA_DIR, f)})

    # Summary
    if os.path.exists(SUMMARY_DIR):
        for f in sorted(os.listdir(SUMMARY_DIR)):
            if patient_id in f and f.endswith(".pdf"):
                files.append({"type": "summary", "name": f,
                               "path": os.path.join(SUMMARY_DIR, f)})

    return jsonify({"patient_id": patient_id, "files": files})


@app.route("/api/download/<patient_id>/<file_type>/<filename>")
def api_download_file(patient_id: str, file_type: str, filename: str):
    """Serve a generated PDF file."""
    if file_type == "report":
        directory = os.path.join(REPORTS_DIR, patient_id)
    elif file_type == "persona":
        directory = PERSONA_DIR
    elif file_type == "summary":
        directory = SUMMARY_DIR
    else:
        return jsonify({"error": "Invalid file type"}), 400
    
    return send_from_directory(directory, filename)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 5000))
    print(f"\n🌐 PD Generator API Server starting on http://localhost:{port}")
    print(f"   Open ui/index.html in your browser to use the interface.\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
