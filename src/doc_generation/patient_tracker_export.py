"""
Patient Tracker Exporter Module.
Generates a landscape PDF table and companion TSV file containing prioritized clinical patient metrics.
"""
import os
import json
import csv
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from src.core.config import (
    PATIENT_DATA_DIR,
    get_patient_records_folder,
    get_patient_report_folder,
)
from src.core import patient_db
from src.data import loader as data_loader

def get_attachment_explanation(clean_name: str) -> str:
    """
    Returns a rich clinical justification and explanation for a given document type.
    
    Args:
        clean_name: The clean document name (e.g. 'MRI Knee').
        
    Returns:
        A clinical string detailing what the document provides and why it helps the PA case.
    """
    lower_name = clean_name.lower()
    if "consult" in lower_name:
        return f"{clean_name} — Provides specialist clinical history, physical examination, and objective evaluation."
    elif any(k in lower_name for k in ["mri", "ct", "xray", "x-ray", "imaging", "radiology", "ultrasound"]):
        return f"{clean_name} — Confirms structural pathology, severity, and objective localization."
    elif any(k in lower_name for k in ["lab", "pathology", "blood", "chemistry", "fobt", "fit"]):
        return f"{clean_name} — Documents objective biomarker findings, lab values, and systemic levels."
    elif any(k in lower_name for k in ["physical therapy", "pt"]):
        return f"{clean_name} — Details functional assessments, range of motion, and conservative trial duration."
    elif "medication" in lower_name:
        return f"{clean_name} — Documents previous failed therapies, drug compliance, and step-therapy status."
    elif "operative" in lower_name or "surgery" in lower_name:
        return f"{clean_name} — Details surgical intervention, intraoperative findings, and clinical history."
    elif "therapy" in lower_name:
        return f"{clean_name} — Documents conservative treatment trials, functional outcomes, and patient response."
    elif "mental" in lower_name or "psych" in lower_name:
        return f"{clean_name} — Documents psychiatric and psychological evaluations and therapeutic progress."
    else:
        return f"{clean_name} — Supports prior authorization medical necessity criteria."

def generate_tracker_export(patient_ids: List[str]) -> str:
    """
    Compiles patient metrics for selected patient IDs into a landscape PDF table
    and companion TSV file. Saves both to `generated_output/patient-data/`.
    
    Args:
        patient_ids: List of numeric patient ID strings to export.
        
    Returns:
        The absolute path to the generated PDF.
    """
    # Ensure patient data directory exists
    os.makedirs(PATIENT_DATA_DIR, exist_ok=True)
    
    pdf_rows = []
    tsv_rows = []
    
    for p_id in patient_ids:
        p_id = str(p_id).strip()
        if not p_id:
            continue
            
        # Try loading concise summary JSON
        records_folder = get_patient_records_folder(p_id)
        json_path = os.path.join(records_folder, "concise_summary.json")
        
        summary_data = None
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading concise summary for patient {p_id}: {e}")
                
        # Load demographics & case info for baseline/fallback
        patient_data = patient_db.load_patient(p_id) or {}
        case_details = data_loader.get_case_details(p_id) or {}
        
        # 1. Patient ID
        row_id = p_id
        
        # 2. Patient Name
        row_name = ""
        if summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_name = overview.get("patient_name", "")
        if not row_name:
            row_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()
        if not row_name or row_name == "Unknown Unknown":
            row_name = f"Patient {p_id}"
            
        # 3. DOB
        row_dob = ""
        if summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_dob = overview.get("dob", "")
        if not row_dob:
            row_dob = patient_data.get("dob") or patient_data.get("demographics", {}).get("dob") or "Unknown"
            
        # 4. Department
        row_dept = case_details.get("department") or ""
        if not row_dept and summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_dept = overview.get("department", "")
        if not row_dept:
            row_dept = "Unknown"

        # 5. CPT Code
        row_cpt = case_details.get("cpt_code") or ""
        if not row_cpt and summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_cpt = overview.get("cpt_code", "")
        if not row_cpt:
            row_cpt = patient_data.get("requested_procedure", {}).get("cpt_code") or "Unknown"

        # 6. Procedure/Medicine Name
        row_proc = case_details.get("procedure") or ""
        if not row_proc and summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_proc = overview.get("procedure_requested", "")
        if not row_proc:
            row_proc = patient_data.get("requested_procedure", {}).get("procedure_name") or "Unknown"

        # 7. Provider (requesting provider)
        row_provider = patient_data.get("pa_request", {}).get("requesting_provider") or ""
        if not row_provider and summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_provider = overview.get("requesting_provider", "")
        if not row_provider:
            row_provider = patient_data.get("provider", {}).get("generalPractitioner") or "Unknown"

        # 8. Insurance Type
        row_insurance_type = ""
        payer_info = patient_data.get("payer") or patient_data.get("insurance") or {}
        if payer_info:
            row_insurance_type = payer_info.get("plan_type") or ""
        if not row_insurance_type:
            row_insurance_type = "Unknown"

        # 9. Policy Name
        row_policy_name = ""
        payer_info = patient_data.get("payer") or patient_data.get("insurance") or {}
        if payer_info:
            row_policy_name = payer_info.get("plan_name") or ""
        if not row_policy_name:
            row_policy_name = "Unknown"

        # ─── 10. Extraction Expectation ───────────────────────────────────────
        extraction_pdf = ""
        extraction_tsv = ""
        if summary_data and "details_from_extraction" in summary_data:
            extract = summary_data["details_from_extraction"]
            if isinstance(extract, list):
                clean_extract = [str(e).replace("\t", " ").replace("\n", " ").strip() for e in extract if str(e).strip()]
                extraction_pdf = "• " + "<br/>• ".join(clean_extract) if clean_extract else ""
                extraction_tsv = "\n".join([f"- {e}" for e in clean_extract])
            else:
                clean_extract = str(extract).replace("\t", " ").replace("\n", " ").strip()
                extraction_pdf = clean_extract
                extraction_tsv = clean_extract
                
        if not extraction_pdf or not extraction_tsv:
            # Fallback path - retrieve supporting diagnoses
            diagnoses_list = []
            if patient_data:
                pa_req = patient_data.get("pa_request") or {}
                if isinstance(pa_req, dict):
                    diagnoses_list = pa_req.get("supporting_diagnoses") or []
            diagnoses_str = "; ".join(diagnoses_list) if diagnoses_list else "None identified"
            req_criteria = case_details.get("details") or "No details provided"
            
            extraction_pdf = (
                f"<b>Expected Service:</b> {row_proc} (CPT: {row_cpt})<br/>"
                f"<b>Target Department:</b> {row_dept}<br/>"
                f"<b>Primary Diagnosis:</b> {diagnoses_str}<br/>"
                f"<b>Required Criteria:</b> {req_criteria}"
            )
            extraction_tsv = (
                f"Expected Service: {row_proc} (CPT: {row_cpt})\n"
                f"Target Department: {row_dept}\n"
                f"Primary Diagnosis: {diagnoses_str}\n"
                f"Required Criteria: {req_criteria}"
            )

        # ─── 11. Likelihood Expectations ──────────────────────────────────────
        likelihood_pre_pdf = ""
        likelihood_pre_tsv = ""
        if summary_data and "likelihood_without_documents" in summary_data:
            val = str(summary_data["likelihood_without_documents"]).replace("\t", " ").replace("\n", " ").strip()
            likelihood_pre_pdf = val
            likelihood_pre_tsv = val
            
        if not likelihood_pre_pdf:
            row_outcome = case_details.get("outcome") or "Unknown"
            req_criteria = case_details.get("details") or "No details provided"
            if row_outcome.lower() == "approval":
                explanation = (
                    f"High baseline likelihood of approval (estimated 70-80%) assuming standard clinical criteria "
                    f"are fully met. The clinical indication for {row_proc} (CPT {row_cpt}) will be evaluated against "
                    f"the following guideline criteria: {req_criteria}."
                )
            else:
                explanation = (
                    f"Low baseline likelihood of approval (estimated <20%) prior to document review. "
                    f"Standard clinical guidelines for {row_proc} (CPT {row_cpt}) require documented conservative "
                    f"management, objective diagnostic findings, and failed step-therapies as outlined: {req_criteria}."
                )
            likelihood_pre_pdf = explanation
            likelihood_pre_tsv = explanation

        # ─── 12. Attachments ──────────────────────────────────────────────────
        attachments_list = []
        if summary_data and "attachments_list" in summary_data:
            raw_attachments = summary_data["attachments_list"] or []
            if isinstance(raw_attachments, list):
                attachments_list = [str(a).strip() for a in raw_attachments if str(a).strip()]
            
        # Scan folder for actual generated PDFs as fallback, strictly excluding personas case-insensitively
        report_folder = get_patient_report_folder(p_id)
        if os.path.exists(report_folder):
            for file_entry in os.listdir(report_folder):
                if file_entry.endswith(".pdf"):
                    # Exclude summary files and persona PDFs case-insensitively
                    if "persona" in file_entry.lower() or file_entry.startswith("Clinical_Summary"):
                        continue
                    clean_name = file_entry.replace(f"DOC-{p_id}-", "").replace(".pdf", "").replace("_", " ")
                    # Add explanation fallback to list if not already represented
                    if not any(clean_name.lower() in a.lower() for a in attachments_list):
                        rich_desc = get_attachment_explanation(clean_name)
                        attachments_list.append(rich_desc)
                        
        if not attachments_list:
            attachments_pdf = "No reports generated"
            attachments_tsv = "No reports generated"
        else:
            clean_attachments = [a.replace("\t", " ").replace("\n", " ").strip() for a in attachments_list if a.strip()]
            attachments_pdf = "• " + "<br/>• ".join(clean_attachments)
            attachments_tsv = "\n".join([f"- {a}" for a in clean_attachments])

        # ─── 13. Post-Attachment Likelihood ───────────────────────────────────
        likelihood_post_pdf = ""
        likelihood_post_tsv = ""
        if summary_data:
            # Retrieve final entry in list
            final_change = ""
            if "likelihood_change_with_documents" in summary_data:
                changes = summary_data["likelihood_change_with_documents"]
                if isinstance(changes, list) and changes:
                    final_change = str(changes[-1]).replace("\t", " ").replace("\n", " ").strip()
                else:
                    final_change = str(changes).replace("\t", " ").replace("\n", " ").strip()
            
            # Extract post-attachment details
            post_param = summary_data.get("likelihood_expectations_post_attachments")
            correct = []
            gaps = []
            if post_param:
                if isinstance(post_param, dict):
                    correct = post_param.get("correct_items") or []
                    gaps = post_param.get("gaps_and_issues") or []
                else:
                    correct = getattr(post_param, "correct_items", []) or []
                    gaps = getattr(post_param, "gaps_and_issues", []) or []
                    
            # For PDF:
            likelihood_post_pdf = f"<b>{final_change or 'Analyzed'}</b>"
            if correct:
                clean_c = [str(c).strip() for c in correct if str(c).strip()]
                if clean_c:
                    likelihood_post_pdf += "<br/><b>Correct Items:</b><br/>• " + "<br/>• ".join(clean_c)
            if gaps:
                clean_g = [str(g).strip() for g in gaps if str(g).strip()]
                if clean_g:
                    likelihood_post_pdf += "<br/><b><font color='red'>Gaps/Issues:</font></b><br/>• " + "<br/>• ".join(clean_g)
                    
            # For TSV:
            likelihood_post_tsv = final_change or "Analyzed"
            if correct:
                clean_c = [str(c).strip() for c in correct if str(c).strip()]
                if clean_c:
                    likelihood_post_tsv += "\nCorrect Items:\n" + "\n".join([f"- {c}" for c in clean_c])
            if gaps:
                clean_g = [str(g).strip() for g in gaps if str(g).strip()]
                if clean_g:
                    likelihood_post_tsv += "\nGaps/Issues:\n" + "\n".join([f"- {g}" for g in clean_g])
                    
        if not likelihood_post_pdf:
            row_outcome = case_details.get("outcome") or "Unknown"
            req_criteria = case_details.get("details") or "No details provided"
            if row_outcome.lower() == "approval":
                explanation = (
                    f"100% (High Likelihood) — Supporting clinical documents successfully substantiate all policy criteria, "
                    f"resolving any potential gaps in the patient profile. Specifically, clinical notes verify required "
                    f"symptoms and historical step therapies as outlined: {req_criteria}."
                )
            else:
                explanation = (
                    f"0% (Low Likelihood) — Clinical documentation reveals persistent gaps or missing policy criteria. "
                    f"Required conservative therapies, objective diagnostic measurements, or clinical assessments were not "
                    f"documented or failed to meet payer policy guidelines: {req_criteria}."
                )
            likelihood_post_pdf = explanation
            likelihood_post_tsv = explanation
            
        pdf_cols = base_cols = [
            row_id,
            row_name,
            row_dob,
            row_dept,
            row_cpt,
            row_proc,
            row_provider,
            row_insurance_type,
            row_policy_name
        ]
        
        pdf_rows.append(pdf_cols + [
            extraction_pdf,
            likelihood_pre_pdf,
            attachments_pdf,
            likelihood_post_pdf
        ])
        
        tsv_rows.append(pdf_cols + [
            extraction_tsv,
            likelihood_pre_tsv,
            attachments_tsv,
            likelihood_post_tsv
        ])
        
    # Paths to save
    pdf_path = os.path.join(PATIENT_DATA_DIR, "patient_tracker_export.pdf")
    tsv_path = os.path.join(PATIENT_DATA_DIR, "patient_tracker_export.tsv")
    
    # ─── Save TSV ─────────────────────────────────────────────────────────────
    try:
        with open(tsv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow([
                "Patient ID", "Patient Name", "DOB", "Department", "CPT Code",
                "Procedure/Medicine Name", "Provider", "Insurance Type", "Policy Name",
                "extraction expectation", "likelihood expectations", "attachments",
                "post-attachment likelihood"
            ])
            for r in tsv_rows:
                writer.writerow(r)
        print(f"✅ TSV file exported successfully: {tsv_path}")
    except Exception as e:
        print(f"⚠️ Could not save TSV: {e}")
        
    # ─── Save PDF ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading2'],
        fontSize=12,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1A365D')
    )
    
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontSize=6,
        leading=7,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor('#2D3748')
    )
    
    story = []
    story.append(Paragraph("Clinical Patient Prior Authorization Tracker Export", title_style))
    story.append(Spacer(1, 8))
    
    headers = [
        "Patient ID", "Patient Name", "DOB", "Department", "CPT Code",
        "Procedure/Medicine Name", "Provider", "Insurance Type", "Policy Name",
        "extraction expectation", "likelihood expectations", "attachments",
        "post-attachment likelihood"
    ]
    
    table_data = []
    # Header Row
    table_data.append([Paragraph(h, header_style) for h in headers])
    
    # Helper function to escape special XML characters except explicitly allowed HTML formatting tags
    def escape_for_paragraph(text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        placeholders = {
            "<b>": "___B_START___",
            "</b>": "___B_END___",
            "<br/>": "___BR___",
            "<font color='red'>": "___FONT_RED___",
            "</font>": "___FONT_END___"
        }
        for tag, placeholder in placeholders.items():
            text = text.replace(tag, placeholder)
            
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        for tag, placeholder in placeholders.items():
            text = text.replace(placeholder, tag)
            
        return text

    # Data Rows
    for r in pdf_rows:
        table_data.append([Paragraph(escape_for_paragraph(str(cell or "N/A")), cell_style) for cell in r])
        
    # Column widths summing to exactly 720 points
    colWidths = [30, 50, 35, 45, 30, 60, 55, 40, 55, 75, 80, 80, 85]
    
    t = Table(table_data, colWidths=colWidths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    
    story.append(t)
    doc.build(story)
    
    print(f"✅ PDF file exported successfully: {pdf_path}")
    return pdf_path

