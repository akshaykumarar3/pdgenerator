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
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, BASE_DIR)

# ─── Load env early (same as src/cli.py) ─────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "cred", ".env"))

from src.data import loader as data_loader
from src.core import patient_db
from src.core import insurance_config

# Refresh CPT code mapping from UAT Plan on server startup
try:
    data_loader.refresh_cpt_code_map()
except Exception:
    pass

app = Flask(__name__)
CORS(app)  # Allow all origins so the file:// UI can call us

# ─── Swagger Setup ────────────────────────────────────────────────────────────
from flasgger import Swagger

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

template = {
    "swagger": "2.0",
    "info": {
        "title": "Clinical Data Generator API",
        "description": "REST Services for synthesizing clinical PDFs and Patient Personas.",
        "version": "2.0.0"
    }
}
swagger = Swagger(app, config=swagger_config, template=template)

# ─── In-memory job store ──────────────────────────────────────────────────────
# { job_id: { status, logs: [], error, result } }
_jobs: dict = {}
_jobs_lock = threading.Lock()

from src.core.config import (
    get_patient_report_folder,
    get_patient_records_folder,
)


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
                     behavioral_notes: str,
                     encounters: list, images: list,
                     reports: list, procedures: list,
                     generate_rejection_docs: bool = False,
                     rejection_gaps: str = ""):
    """Background worker: calls the generator and updates job state."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"

    try:
        with JobLogger(job_id):
            from src import workflow as wf

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

            if encounters:
                enc_lines = []
                for e in encounters:
                    enc_lines.append(
                        f"  - [{e.get('type','')}] Date: {e.get('date','')} | "
                        f"Provider: {e.get('provider','')} @ {e.get('facility','')} | "
                        f"Reason: {e.get('reason','')} | Notes: {e.get('notes','')}"
                    )
                extra_blocks.append("CLINICAL ENCOUNTERS (use exactly as provided):\n" + "\n".join(enc_lines))

            if images:
                img_lines = []
                for img in images:
                    img_lines.append(
                        f"  - [{img.get('type','')}] Date: {img.get('date','')} | "
                        f"Facility: {img.get('facility','')} | Ordered by: {img.get('provider','')} | "
                        f"Findings: {img.get('findings','')}"
                    )
                extra_blocks.append("IMAGING STUDIES (use exactly as provided):\n" + "\n".join(img_lines))

            if reports:
                rep_lines = []
                for r in reports:
                    rep_lines.append(
                        f"  - [{r.get('type','')}] Date: {r.get('date','')} | "
                        f"Ordered by: {r.get('provider','')} | Results: {r.get('results','')} | Notes: {r.get('notes','')}"
                    )
                extra_blocks.append("LAB & PATHOLOGY REPORTS (use exactly as provided):\n" + "\n".join(rep_lines))

            if procedures:
                proc_lines = []
                for p in procedures:
                    proc_lines.append(
                        f"  - {p.get('name','')} | Date: {p.get('date','')} | "
                        f"Performed by: {p.get('provider','')} @ {p.get('facility','')} | "
                        f"Indication: {p.get('reason','')} | Notes: {p.get('notes','')}"
                    )
                extra_blocks.append("PROCEDURES (use exactly as provided):\n" + "\n".join(proc_lines))

            if pa_optimize:
                # Ensure reports are generated to support higher approval likelihood
                if generation_mode is not None:
                    generation_mode["reports"] = True
                extra_blocks.append(
                    "PA APPROVAL OPTIMIZATION: Even if clinical outcome is expected denial/low-probability, "
                    "generate all clinical documents with the STRONGEST possible medical justification to "
                    "maximize PA approval probability. Include thorough clinical rationale, all supporting "
                    "evidence, and comprehensive documentation. The annotator summary will still note the "
                    "expected outcome label."
                )

            if generate_rejection_docs:
                if rejection_gaps and rejection_gaps.strip():
                    extra_blocks.append(f"[REJECTION GAPS / DENIAL FOCUS]: {rejection_gaps.strip()}")
                else:
                    extra_blocks.append("[REJECTION GAPS / DENIAL FOCUS]: Ensure the clinical evidence is insufficient. Omit critical supportive findings, exclude documentation of prior conservative treatments, and ensure the criteria for PA approval are explicitly NOT met.")

            combined_feedback = feedback.strip()
            if extra_blocks:
                combined_feedback += ("\n\n" if combined_feedback else "") + "\n\n".join(extra_blocks)

            # Fetch exclusion names
            current_names = patient_db.get_all_patient_names()

            def cancel_check():
                with _jobs_lock:
                    return _jobs[job_id].get("cancelled", False)

            result_name = wf.process_patient_workflow(
                patient_id=patient_id,
                feedback=combined_feedback,
                excluded_names=current_names,
                generation_mode=generation_mode,
                cancel_check=cancel_check,
                archive_token=job_id,
                generate_rejection_docs=generate_rejection_docs
            )

            if cancel_check():
                with _jobs_lock:
                    _jobs[job_id]["logs"].append("⛔ Worker stopped due to cancellation. Performing rollback...")
                from src.utils.file_utils import restore_patient_files
                restore_patient_files(patient_id, generation_mode, archive_token=job_id)
                with _jobs_lock:
                    _jobs[job_id]["status"] = "cancelled"
                    _jobs[job_id]["result"] = "Cancelled by user"
                return

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



def _run_batch_generation(job_id, patients_payload, pa_optimize):
    """Background worker for batch processing specific patients."""
    try:
        def log_cb(msg):
            with _jobs_lock:
                _jobs[job_id]["logs"].append(msg)

        log_cb(f"🚀 Starting BATCH generation for {len(patients_payload)} patients.")

        success_count = 0
        from src.workflow import process_patient_workflow

        for entry in patients_payload:
            p_id = str(entry.get("patient_id", "")).strip()
            if not p_id:
                continue
            generation_mode = entry.get("generation_mode") or {"summary": True, "reports": True, "persona": True}
            feedback = entry.get("feedback", "")
            with _jobs_lock:
                if _jobs[job_id].get("cancelled"):
                    log_cb("⛔ Batch cancelled. Stopping.")
                    break
            
            def cancel_check():
                with _jobs_lock:
                    return _jobs[job_id].get("cancelled", False)

            log_cb(f"\n--- Batch: Processing Patient ID {p_id} ---")
            try:
                import sys, io
                original_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    current_names = patient_db.get_all_patient_names()
                    tok = f"{job_id}_{p_id}"
                    result_name = process_patient_workflow(
                        patient_id=p_id, feedback=feedback,
                        excluded_names=current_names, generation_mode=generation_mode,
                        cancel_check=cancel_check, archive_token=tok
                    )
                finally:
                    output = sys.stdout.getvalue()
                    sys.stdout = original_stdout
                    for line in output.splitlines():
                        if line.strip():
                            log_cb(line)
                            
                if cancel_check():
                    from src.utils.file_utils import restore_patient_files
                    restore_patient_files(p_id, generation_mode, archive_token=tok)
                    break
                    
                success_count += 1
                log_cb(f"✅ {p_id} completed successfully (Result: {result_name})")
            except Exception as pe:
                log_cb(f"❌ Failed processing {p_id}: {pe}")

        with _jobs_lock:
            if _jobs[job_id].get("cancelled"):
                _jobs[job_id]["status"] = "cancelled"
                _jobs[job_id]["result"] = f"Batch Cancelled: {success_count}/{len(patients_payload)} OK"
            else:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = f"Batch Complete: {success_count}/{len(patients_payload)} OK"
                _jobs[job_id]["logs"].append("🏁 Batch run finished.")
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["logs"].append(f"❌ Fatal Batch Exception: {str(e)}")


def _run_preview_generation(job_id: str, patient_id: str, feedback: str,
                             generation_mode: dict, medications: list, allergies: list,
                             vaccinations: list, therapies: list, behavioral_notes: str,
                             encounters: list, images: list, reports: list, procedures: list,
                             generate_rejection_docs: bool = False,
                             rejection_gaps: str = ""):
    """Background worker: AI-only generation, stores payload for preview UI (no PDFs)."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        with JobLogger(job_id):
            from src import workflow as wf

            # Build same combined_feedback as _run_generation
            extra_blocks = []
            if medications:
                med_lines = [
                    f"  - [{m.get('status','current').upper()}] {m.get('brand','')} ({m.get('generic_name','')}) "
                    f"{m.get('dosage','')} | By: {m.get('prescribed_by','')} | Reason: {m.get('reason','')}"
                    for m in medications
                ]
                extra_blocks.append("MEDICATIONS (use exactly as provided):\n" + "\n".join(med_lines))
            if allergies:
                a_lines = [
                    f"  - {a.get('allergen','')} | {a.get('allergy_type','')} | {a.get('reaction','')} | {a.get('severity','')}"
                    for a in allergies
                ]
                extra_blocks.append("ALLERGIES (use exactly as provided):\n" + "\n".join(a_lines))
            if vaccinations:
                v_lines = [
                    f"  - {v.get('vaccine_name','')} | {v.get('date_administered','')} | Reason: {v.get('reason','')}"
                    for v in vaccinations
                ]
                extra_blocks.append("VACCINATIONS (use exactly as provided):\n" + "\n".join(v_lines))
            if therapies:
                t_lines = [
                    f"  - [{t.get('status','active').upper()}] {t.get('therapy_type','')} | {t.get('provider','')} | {t.get('frequency','')}"
                    for t in therapies
                ]
                extra_blocks.append("THERAPY HISTORY (use exactly as provided):\n" + "\n".join(t_lines))
            if behavioral_notes:
                extra_blocks.append(f"BEHAVIORAL NOTES:\n  {behavioral_notes}")
            if encounters:
                e_lines = [
                    f"  - [{e.get('type','')}] Date: {e.get('date','')} | {e.get('provider','')} | {e.get('reason','')}"
                    for e in encounters
                ]
                extra_blocks.append("CLINICAL ENCOUNTERS (use exactly as provided):\n" + "\n".join(e_lines))
            if images:
                i_lines = [
                    f"  - [{i.get('type','')}] Date: {i.get('date','')} | Findings: {i.get('findings','')}"
                    for i in images
                ]
                extra_blocks.append("IMAGING STUDIES (use exactly as provided):\n" + "\n".join(i_lines))
            if reports:
                r_lines = [
                    f"  - [{r.get('type','')}] Date: {r.get('date','')} | Results: {r.get('results','')}"
                    for r in reports
                ]
                extra_blocks.append("LAB & PATHOLOGY REPORTS (use exactly as provided):\n" + "\n".join(r_lines))
            if procedures:
                p_lines = [
                    f"  - {p.get('name','')} | Date: {p.get('date','')} | {p.get('reason','')}"
                    for p in procedures
                ]
                extra_blocks.append("PROCEDURES (use exactly as provided):\n" + "\n".join(p_lines))

            if generate_rejection_docs:
                if rejection_gaps and rejection_gaps.strip():
                    extra_blocks.append(f"[REJECTION GAPS / DENIAL FOCUS]: {rejection_gaps.strip()}")
                else:
                    extra_blocks.append("[REJECTION GAPS / DENIAL FOCUS]: Ensure the clinical evidence is insufficient. Omit critical supportive findings, exclude documentation of prior conservative treatments, and ensure the criteria for PA approval are explicitly NOT met.")

            combined_feedback = feedback.strip()
            if extra_blocks:
                combined_feedback += ("\n\n" if combined_feedback else "") + "\n\n".join(extra_blocks)

            def cancel_check():
                with _jobs_lock:
                    return _jobs[job_id].get("cancelled", False)

            current_names = patient_db.get_all_patient_names()
            payload = wf.preview_patient_generation(
                patient_id=patient_id,
                feedback=combined_feedback,
                excluded_names=current_names,
                generation_mode=generation_mode,
                cancel_check=cancel_check,
                generate_rejection_docs=generate_rejection_docs,
            )

        with _jobs_lock:
            if _jobs[job_id].get("cancelled"):
                _jobs[job_id]["status"] = "cancelled"
                _jobs[job_id]["result"] = "Preview cancelled by user"
                _jobs[job_id]["logs"].append("⛔ Preview generation stopped.")
                return
            
            _jobs[job_id]["status"] = "done" if payload else "error"
            _jobs[job_id]["preview_payload"] = payload
            _jobs[job_id]["result"] = (
                f"Preview ready: {len((payload or {}).get('documents', []))} documents"
                if payload else "Preview generation failed"
            )
            if not payload:
                _jobs[job_id]["error"] = "AI generation returned no payload"
    except Exception as exc:
        err_msg = f"ERROR: {exc}\n{traceback.format_exc()}"
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = err_msg
            _jobs[job_id]["logs"].append(f"❌ {err_msg}")


def _run_generation_from_content(job_id: str, patient_id: str, generation_mode: dict,
                                  documents_content: list, persona_json: dict | None):
    """Background worker: render PDFs from user-confirmed/edited content."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        with JobLogger(job_id):
            from src import workflow as wf
            def cancel_check():
                with _jobs_lock:
                    return _jobs[job_id].get("cancelled", False)

            docs_written = wf.render_patient_pdfs_from_content(
                patient_id=patient_id,
                generation_mode=generation_mode,
                documents_content=documents_content,
                persona_json=persona_json,
                summarize=True,
                cancel_check=cancel_check,
                archive_token=job_id
            )
            
            if cancel_check():
                with _jobs_lock:
                    _jobs[job_id]["logs"].append("⛔ Worker stopped due to cancellation. Performing rollback...")
                from src.utils.file_utils import restore_patient_files
                restore_patient_files(patient_id, generation_mode, archive_token=job_id)
                with _jobs_lock:
                    _jobs[job_id]["status"] = "cancelled"
                    _jobs[job_id]["result"] = "Cancelled by user"
                return
            
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = f"{len(docs_written)} PDF(s) generated"
    except Exception as exc:
        err_msg = f"ERROR: {exc}\n{traceback.format_exc()}"
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = err_msg
            _jobs[job_id]["logs"].append(f"❌ {err_msg}")





@app.route("/api/status")
def api_status():
    """
    Health check.
    ---
    tags:
      - System
    responses:
      200:
        description: Returns server online status
    """
    return jsonify({"ok": True, "timestamp": datetime.now().isoformat()})


@app.route("/api/patients")
def api_patients():
    """
    Return all patient IDs from the Excel plan.
    ---
    tags:
      - Patients
    responses:
      200:
        description: List of patient IDs
    """
    try:
        ids = data_loader.get_all_patient_ids()
        return jsonify({"patients": ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/patient/<patient_id>")
def api_get_patient(patient_id: str):
    """Return the current DB record for a patient plus UAT case details."""
    record = patient_db.load_patient(patient_id)

    # Enrich with case/UAT info from the Excel plan so the UI can show
    # case type, expected outcome, CPT/ICD codes without a separate call.
    case_details: dict | None = None
    try:
        case_details = data_loader.get_case_details(patient_id)
    except Exception:
        pass

    if record or case_details:
        return jsonify({
            "found": bool(record),
            "data": record,
            "case_details": case_details,
        })
    return jsonify({"found": False, "data": None, "case_details": None})


@app.route("/api/insurance/config")
def api_insurance_config():
    """Return insurance configuration for UI selection."""
    return jsonify(insurance_config.get_config())


@app.route("/api/patient/<patient_id>/insurance", methods=["POST"])
def api_update_patient_insurance(patient_id: str):
    """Update patient-level insurance selection."""
    body = request.get_json(force=True) or {}
    provider_id = str(body.get("provider_id", "")).strip()
    plan_type = str(body.get("plan_type", "")).strip()
    plan_id = str(body.get("plan_id", "")).strip() if body.get("plan_id") else None

    provider = insurance_config.get_provider_by_id(provider_id)
    if not provider:
        return jsonify({"error": "Invalid provider_id"}), 400

    if plan_type:
        valid_types = {p.get("plan_type") for p in (provider.get("plans") or [])}
        if plan_type not in valid_types:
            return jsonify({"error": "Invalid plan_type for provider"}), 400

    record = patient_db.load_patient(patient_id) or {}
    record["insurance_selection"] = {
        "provider_id": provider_id,
        "plan_type": plan_type or None,
        "plan_id": plan_id or None,
    }
    patient_db.save_patient(patient_id, record)
    return jsonify({"ok": True, "insurance_selection": record["insurance_selection"]})


@app.route("/api/patient/<patient_id>/insurance", methods=["DELETE"])
def api_clear_patient_insurance(patient_id: str):
    """Clear patient-level insurance selection."""
    record = patient_db.load_patient(patient_id) or {}
    if "insurance_selection" in record:
        del record["insurance_selection"]
    if "payer" in record:
        del record["payer"]
    patient_db.save_patient(patient_id, record)
    return jsonify({"ok": True})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Spawn a background generation job. Returns job_id immediately.
    ---
    tags:
      - Generation
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            patient_id:
              type: string
            generation_mode:
              type: object
            pa_optimize:
              type: boolean
            feedback:
              type: string
    responses:
      202:
        description: Job queued
    """
    body = request.get_json(force=True) or {}
    patient_id     = str(body.get("patient_id", "")).strip()
    feedback       = body.get("feedback", "")
    generation_mode = body.get("generation_mode", {"summary": True, "reports": True, "persona": True})
    pa_optimize    = bool(body.get("pa_optimize", False))
    medications    = body.get("medications", [])
    allergies      = body.get("allergies", [])
    vaccinations   = body.get("vaccinations", [])
    therapies      = body.get("therapies", [])
    encounters     = body.get("encounters", [])
    images         = body.get("images", [])
    reports        = body.get("reports", [])
    procedures     = body.get("procedures", [])
    behavioral_notes = body.get("behavioral_notes", "")
    generate_rejection_docs = bool(body.get("generate_rejection_docs", False))
    rejection_gaps = str(body.get("rejection_gaps", "")).strip()

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
                "encounter_count": len(encounters),
                "image_count": len(images),
                "report_count": len(reports),
                "procedure_count": len(procedures),
                "has_behavioral_notes": bool(behavioral_notes),
            }
        }

    t = threading.Thread(
        target=_run_generation,
        args=(job_id, patient_id, feedback, generation_mode, pa_optimize,
              medications, allergies, vaccinations, therapies, behavioral_notes,
              encounters, images, reports, procedures, generate_rejection_docs, rejection_gaps),
        daemon=True
    )
    t.start()

    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Spawn AI-only generation job and return payload for preview editor (no PDFs written)."""
    body = request.get_json(force=True) or {}
    patient_id = str(body.get("patient_id", "")).strip()
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    feedback         = body.get("feedback", "")
    generation_mode  = body.get("generation_mode", {"persona": True, "reports": True, "summary": False})
    medications      = body.get("medications", [])
    allergies        = body.get("allergies", [])
    vaccinations     = body.get("vaccinations", [])
    therapies        = body.get("therapies", [])
    behavioral_notes = body.get("behavioral_notes", "")
    encounters       = body.get("encounters", [])
    images           = body.get("images", [])
    reports          = body.get("reports", [])
    procedures       = body.get("procedures", [])
    generate_rejection_docs = bool(body.get("generate_rejection_docs", False))
    rejection_gaps = str(body.get("rejection_gaps", "")).strip()

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "logs": [f"🔍 Preview job {job_id} queued for patient {patient_id}"],
            "error": None,
            "result": None,
            "preview_payload": None,
            "patient_id": patient_id,
            "created_at": datetime.now().isoformat(),
            "request_context": {"source": "preview"},
        }

    t = threading.Thread(
        target=_run_preview_generation,
        args=(job_id, patient_id, feedback, generation_mode, medications, allergies,
              vaccinations, therapies, behavioral_notes, encounters, images, reports, procedures,
              generate_rejection_docs, rejection_gaps),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/generate_from_content", methods=["POST"])
def api_generate_from_content():
    """Generate PDFs from user-confirmed (possibly edited) document content."""
    body = request.get_json(force=True) or {}
    patient_id = str(body.get("patient_id", "")).strip()
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    generation_mode   = body.get("generation_mode", {"persona": True, "reports": True, "summary": True})
    documents_content = body.get("documents", [])   # [{title_hint, content_html}]
    persona_json      = body.get("persona", None)

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "logs": [f"📄 PDF rendering job {job_id} queued for patient {patient_id}"],
            "error": None,
            "result": None,
            "patient_id": patient_id,
            "created_at": datetime.now().isoformat(),
            "request_context": {"source": "generate_from_content"},
        }

    t = threading.Thread(
        target=_run_generation_from_content,
        args=(job_id, patient_id, generation_mode, documents_content, persona_json),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/generate_all", methods=["POST"])
def api_generate_all():
    """
    Spawn a background batch generation job for all patients.
    ---
    tags:
      - Generation
    responses:
      202:
        description: Batch Job queued
    """
    body = request.get_json(force=True) or {}
    patients_payload = body.get("patients", None)
    pa_optimize = bool(body.get("pa_optimize", False))

    normalized = []
    if patients_payload:
        for entry in patients_payload:
            pid = str(entry.get("patient_id", "")).strip()
            if not pid:
                continue
            generation_mode = entry.get("generation_mode") or body.get(
                "generation_mode",
                {"summary": True, "reports": True, "persona": True},
            )
            feedback = entry.get("feedback")
            if feedback is None or str(feedback).strip() == "":
                feedback = body.get("feedback", "")
            normalized.append({
                "patient_id": pid,
                "generation_mode": generation_mode,
                "feedback": feedback,
            })
    else:
        patient_ids = body.get("patient_ids", [])
        if not patient_ids:
            return jsonify({"error": "patient_ids is required and cannot be empty"}), 400
        feedback = body.get("feedback", "")
        generation_mode = body.get("generation_mode", {"summary": True, "reports": True, "persona": True})
        normalized = [
            {"patient_id": str(pid), "generation_mode": generation_mode, "feedback": feedback}
            for pid in patient_ids
        ]

    if not normalized:
        return jsonify({"error": "patients payload is empty"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "logs": [f"🚀 BATCH Job {job_id} queued for {len(normalized)} patients"],
            "error": None,
            "result": None,
            "changes_summary": None,
            "patient_id": "BATCH",
            "created_at": datetime.now().isoformat(),
            "request_context": {
                "feedback": body.get("feedback", ""),
                "generation_mode": body.get("generation_mode", None),
                "pa_optimize": pa_optimize,
                "is_batch": True
            }
        }

    t = threading.Thread(
        target=_run_batch_generation,
        args=(job_id, normalized, pa_optimize),
        daemon=True
    )
    t.start()

    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/job/<job_id>")
def api_job_status(job_id: str):
    """
    Poll job status + latest log lines.
    ---
    tags:
      - Generation
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
    responses:
      200:
        description: Job details and logs
    """
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
        "all_logs": job["logs"],
        "preview_payload": job.get("preview_payload"),   # populated by /api/preview jobs
    })

@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel_job(job_id: str):
    """
    Cancel an active job and trigger rollback of generated outputs.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    with _jobs_lock:
        if job["status"] in ["done", "error", "cancelled"]:
            return jsonify({"job_id": job_id, "status": job["status"]}) # Already finished
        
        job["cancelled"] = True
        job["status"] = "cancelled"
        job["logs"].append("⛔ Cancellation requested by user.")

    return jsonify({"job_id": job_id, "status": "cancelled"})


@app.route("/api/output/<patient_id>")
def api_output(patient_id: str):
    """
    List all generated output files for a patient.
    ---
    tags:
      - Output
    parameters:
      - in: path
        name: patient_id
        type: string
        required: true
    responses:
      200:
        description: Files array
    """
    files = []

    root_folder = get_patient_report_folder(patient_id)
    if os.path.exists(root_folder):
        for f in sorted(os.listdir(root_folder)):
            if not f.endswith(".pdf"):
                continue
            full_path = os.path.join(root_folder, f)
            if not os.path.isfile(full_path):
                continue
            if f.startswith(f"DOC-{patient_id}-"):
                files.append({"type": "report", "name": f, "path": full_path})
            elif "-persona" in f and f.startswith(f"{patient_id}-"):
                files.append({"type": "persona", "name": f, "path": full_path})
            elif f.startswith(f"Clinical_Summary_Patient_{patient_id}"):
                files.append({"type": "summary", "name": f, "path": full_path})

    return jsonify({"patient_id": patient_id, "files": files})


@app.route("/api/record/<patient_id>")
def api_get_patient_record(patient_id: str):
    """Return the human-readable patient text record."""
    record_path = os.path.join(get_patient_records_folder(patient_id), f"{patient_id}-record.txt")
    if not os.path.exists(record_path):
        return jsonify({"error": "Record not found", "patient_id": patient_id}), 404
    with open(record_path, "r", encoding="utf-8") as f:
        content = f.read()
    return jsonify({"patient_id": patient_id, "record": content})


@app.route("/api/download/<patient_id>/<file_type>/<filename>")
def api_download_file(patient_id: str, file_type: str, filename: str):
    """Serve a generated PDF file."""
    if file_type == "report":
        directory = get_patient_report_folder(patient_id)
    elif file_type == "persona":
        directory = get_patient_report_folder(patient_id)
    elif file_type == "summary":
        directory = get_patient_report_folder(patient_id)
    else:
        return jsonify({"error": "Invalid file type"}), 400
    
    # Force inline viewing by explicitly setting mimetype and disposition
    return send_from_directory(directory, filename, mimetype='application/pdf', as_attachment=False)


@app.route("/api/purge", methods=["POST"])
def api_purge():
    """
    Purge specific databases or generated files
    ---
    tags:
      - System
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            target:
              type: string
              enum: [all, personas, documents, summaries_only, reports_only, patient]
            patient_id:
              type: string
            mode:
              type: string
              enum: [delete, archive]
            targets:
              type: array
              items:
                type: string
              description: "For target=patient: persona, reports, summary, logs, db, records, debug"
    responses:
      200:
        description: Purge successful
    """
    from src.utils import purge_manager
    body = request.get_json(force=True) or {}
    target = body.get("target")

    try:
        if target == "all":
            purge_manager.purge_all(force=True)
        elif target == "personas":
            purge_manager.purge_personas(force=True)
        elif target == "documents":
            purge_manager.purge_documents(force=True)
        elif target == "summaries_only":
            purge_manager.purge_summaries_only(force=True)
        elif target == "reports_only":
            purge_manager.purge_reports_only(force=True)
        elif target == "patient":
            p_id = body.get("patient_id")
            if not p_id:
                return jsonify({"error": "patient_id required"}), 400
            mode = body.get("mode", "delete")
            targets = body.get("targets")
            if targets:
                purge_manager.purge_patient_selective(p_id, targets, mode=mode, force=True)
            else:
                purge_manager.purge_patient(p_id, force=True)
        else:
            return jsonify({"error": "Invalid target"}), 400
            
        return jsonify({"ok": True, "message": f"Purged {target} successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/template/save", methods=["POST"])
def api_save_template():
    """
    Save a generated document as a global template
    ---
    tags:
      - Templates
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            patient_id:
              type: string
            file_type:
              type: string
            filename:
              type: string
    responses:
      200:
        description: Document saved as template
    """
    import shutil, time
    body = request.get_json(force=True) or {}
    patient_id = body.get("patient_id")
    file_type = body.get("file_type")
    filename = body.get("filename")

    if not all([patient_id, file_type, filename]):
        return jsonify({"error": "Missing parameters"}), 400

    base_dir = ""
    if file_type == "persona":
        base_dir = get_patient_report_folder(patient_id)
    elif file_type == "report":
        base_dir = get_patient_report_folder(patient_id)
    elif file_type == "summary":
        base_dir = get_patient_report_folder(patient_id)
    
    source_path = os.path.join(base_dir, filename)
    if not os.path.exists(source_path):
        return jsonify({"error": "Source file not found"}), 404

    try:
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        archive_dir = os.path.join(templates_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)

        # File will be saved as template_persona.pdf, template_report.pdf, template_summary.pdf
        target_name = f"template_{file_type}.pdf"
        target_path = os.path.join(templates_dir, target_name)

        if os.path.exists(target_path):
            timestamp = int(time.time())
            archived_name = f"template_{file_type}_archived_{timestamp}.pdf"
            shutil.move(target_path, os.path.join(archive_dir, archived_name))

        shutil.copy2(source_path, target_path)
        return jsonify({"ok": True, "message": f"Saved {target_name}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 410))
    print(f"\n🌐 PD Generator API Server starting on http://localhost:{port}")
    print(f"   Open ui/index.html in your browser to use the interface.\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
